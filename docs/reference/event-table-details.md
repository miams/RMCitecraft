# RootsMagic 11: EventTable.Details Field

**Document Version:** 1.0
**Last Updated:** 2025-01-08
**Related Tables:** EventTable, FactTypeTable
**Field:** EventTable.Details (TEXT)

---

## Overview

The `EventTable.Details` field stores **free-form text** descriptions for events. Unlike BLOB fields with XML structure, Details is simple unstructured text providing additional information about an event.

### Key Facts

- **Format:** Plain text (no XML, no special encoding)
- **Usage:** 21.4% of events have Details content
- **Length:** Varies from a few characters to paragraphs
- **Content:** Event-specific information, descriptions, identifiers

---

## Usage by Event Type

### High Usage Event Types (>70%)

| Event Type | Usage | Typical Content |
|------------|-------|-----------------|
| War Veteran | 100% | War name (e.g., "Vietnam War", "World War II") |
| War Military Branch | 100% | Branch name (e.g., "U.S. Army", "Navy") |
| War Unit | 100% | Unit designation (e.g., "4100th Unit, Patterson Field") |
| War Rank | 100% | Military rank (e.g., "Private", "Lieutenant") |
| War Notables | 100% | Awards, medals (e.g., "Purple Heart", "Bronze Star") |
| Soc Sec No | 99.6% | SSN (e.g., "274-12-5427") |
| News | 97.5% | Newspaper name (e.g., "Muncie Evening Press") |
| Occupation | 96.8% | Job title (e.g., "farmer", "teacher", "engineer") |
| Obituary | 77.8% | Newspaper/publication name |

### Medium Usage Event Types (10-70%)

| Event Type | Usage | Typical Content |
|------------|-------|-----------------|
| Property | 72% | Property description, value |
| Land Transaction | 71.8% | Transaction details, acreage, price |
| Miscellaneous | 71.6% | Various descriptive text |
| Probate | 56.5% | Court, case details |
| Burial | 25.8% | Cemetery details, plot information |
| Biography | 17% | Biographical notes |
| Will | 13.6% | Document type (e.g., "codicil") |
| Residence | 13.6% | Address details |

### Low Usage Event Types (<10%)

| Event Type | Usage | Typical Content |
|------------|-------|-----------------|
| Death | 5.2% | Cause of death (e.g., "nephritis", "acute myocardial ischemia") |
| Birth | 0.6% | Birth circumstances (rare) |
| Census | 0.1% | Census details (very rare) |

---

## Content Patterns

### Pattern 1: Identifiers

**Social Security Numbers:**
```
274-12-5427
187-36-7279
```

### Pattern 2: Names/Titles

**Occupations:**
```
farmer
teacher
petroleum engineer
```

**Military Branches:**
```
U.S. Army
Navy
Marine Corps
```

**Publications:**
```
Muncie Evening Press
Indianapolis News
Daily American Republic
```

### Pattern 3: Descriptions

**Cause of Death:**
```
nephritis
acute myocardial ischemia
intestinal cancer
```

**Military Units:**
```
4100th Unit, Patterson Field, Ohio
USS Fletcher
28th Infantry Division
```

**Land Transactions:**
```
He bought another part of "Burgess Choice" (61 acres) for £55 from Benjamin Burgess.
```

### Pattern 4: Awards/Honors

**Military:**
```
Purple Heart
Bronze Star
Distinguished Service Medal
```

---

## Relationship to FactTypeTable.UseValue

The `FactTypeTable.UseValue` field indicates whether Details should be used:

| UseValue | Meaning | Example Event Types |
|----------|---------|---------------------|
| 0 | Details not typically used | Birth, Marriage, Baptism |
| 1 | Details field is used | Death (cause), Occupation (job), SSN (number) |

**Query to check:**
```sql
SELECT FactTypeID, Name, UseValue
FROM FactTypeTable
WHERE UseValue = 1;
```

---

## Querying Details

### Get Events with Details

```sql
SELECT
    e.EventID,
    ft.Name as EventType,
    e.Date,
    e.Details,
    pl.Name as Place
FROM EventTable e
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
WHERE e.OwnerType = 0
  AND e.OwnerID = ?  -- PersonID
  AND e.Details IS NOT NULL
  AND e.Details != ''
ORDER BY e.SortDate;
```

### Search Details Content

```sql
-- Find events with specific Details content
SELECT
    e.EventID,
    ft.Name as EventType,
    p.PersonID,
    n.Surname || ', ' || n.Given as Name,
    e.Details
FROM EventTable e
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
JOIN PersonTable p ON e.OwnerID = p.PersonID
JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
WHERE e.OwnerType = 0
  AND e.Details LIKE '%farmer%'
ORDER BY n.Surname, n.Given;
```

---

## Using Details in Narratives

### Death Event

**Data:**
```
Event: Death
Date: 3 January 1920
Place: Baltimore, Maryland
Details: pneumonia
```

**Narrative:**
> John Smith died of pneumonia on January 3, 1920, in Baltimore, Maryland.

### Occupation Event

**Data:**
```
Event: Occupation
Date: 1880
Place: Adams County, Pennsylvania
Details: farmer
```

**Narrative:**
> In 1880, John Smith worked as a farmer in Adams County, Pennsylvania.

### Military Service

**Data:**
```
Event: War Unit
Details: 4100th Unit, Patterson Field, Ohio
```

**Narrative:**
> He served in the 4100th Unit, stationed at Patterson Field, Ohio.

---

## Python: Extract Details

```python
def get_event_details(event_id, conn):
    """
    Get Details field for an event.

    Args:
        event_id: EventID from EventTable
        conn: Database connection

    Returns:
        str: Details text or None
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT Details
        FROM EventTable
        WHERE EventID = ?
    """, (event_id,))

    result = cursor.fetchone()
    if result and result[0]:
        return result[0].strip()

    return None
```

### Incorporate Details in Event Description

```python
def format_event_with_details(event_data):
    """
    Format event with Details field incorporated.

    Args:
        event_data: Dict with event information

    Returns:
        str: Formatted event description
    """
    event_type = event_data['type_name']
    details = event_data.get('details', '').strip()

    # Death with cause
    if event_type == 'Death' and details:
        return f"died of {details}"

    # Occupation
    if event_type == 'Occupation' and details:
        article = 'an' if details[0].lower() in 'aeiou' else 'a'
        return f"worked as {article} {details}"

    # Military branch
    if event_type == 'War Military Branch' and details:
        return f"served in the {details}"

    # Generic - append details if present
    if details:
        return f"{event_type}: {details}"

    return event_type
```

---

## Data Quality Considerations

### Empty vs NULL

Both NULL and empty string ('') indicate no Details:

```sql
-- Count truly empty Details
SELECT COUNT(*)
FROM EventTable
WHERE Details IS NULL OR Details = '';
```

### Leading/Trailing Whitespace

Always trim Details when displaying:

```python
details = event['details'].strip() if event['details'] else None
```

### Validation

Check for reasonable content:

```python
def validate_details(event_type, details):
    """Validate Details content for event type."""

    if not details:
        return True  # Empty is acceptable

    # SSN should be 11 characters (###-##-####)
    if event_type == 'Soc Sec No':
        return len(details) == 11 and details.count('-') == 2

    # Occupation shouldn't be too long
    if event_type == 'Occupation':
        return len(details) < 100

    return True
```

---

## Common Patterns by Event Type

| Event Type | Details Content | Format |
|------------|-----------------|--------|
| Soc Sec No | SSN | ###-##-#### |
| Occupation | Job title | Text (typically 1-3 words) |
| Death | Cause | Text (medical term or description) |
| War Veteran | War name | Text (e.g., "World War II") |
| War Branch | Branch name | Text (e.g., "U.S. Army") |
| War Unit | Unit designation | Text (may include location) |
| War Rank | Military rank | Text (e.g., "Private") |
| News | Newspaper name | Text |
| Obituary | Publication | Text |
| Burial | Cemetery details | Text (location, plot) |
| Property | Value/description | Text (may include amounts) |

---

## Notes for AI Agents

1. **Details is optional** - 78.6% of events have no Details

2. **No special parsing** - Unlike BLOBs, Details is plain text

3. **Event type determines content** - Details meaning varies by FactType

4. **Check UseValue first** - FactTypeTable.UseValue=1 indicates Details is expected

5. **Include in narratives** - When present, Details enriches event descriptions

6. **Trim whitespace** - Always strip leading/trailing spaces

7. **Validate by type** - SSNs have format, occupations have reasonable length

8. **Empty checks** - Test for both NULL and empty string

9. **Search capability** - Details can be searched with LIKE queries

10. **Context matters** - "farmer" in Occupation vs "farmer" in Burial have different meanings

---

## Related Documentation

- **RM11_Schema_Reference.md** - EventTable schema
- **RM11_FactTypes.md** - Event types and UseValue
- **RM11_Biography_Best_Practices.md** - Using Details in narratives
- **RM11_Sentence_Templates.md** - [Desc] variable references Details

---

## Summary

The `EventTable.Details` field provides **unstructured supplementary information** for events:

- **Plain text** (no XML parsing required)
- **21.4% usage rate** (optional for most events)
- **Event-type specific** content (SSN numbers, job titles, causes of death, military units)
- **Used by narrative generation** via [Desc] template variable
- **Simple to query and display** - just trim whitespace

For events with `FactTypeTable.UseValue=1`, Details provides crucial context that enriches biographical narratives beyond just date, place, and event type.

---

**End of Document**
