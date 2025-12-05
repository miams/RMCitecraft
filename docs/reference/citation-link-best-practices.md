---
priority: reference
topics: [database, citation, findagrave, testing, ui]
---

# CitationLinkTable Best Practices

**Empirical Analysis of RootsMagic Database Citation Linking Patterns**

This document provides best practices for creating CitationLinkTable records based on analysis of existing RootsMagic databases. The schema documentation lists some fields as "Not Implemented," but empirical analysis reveals they are **critical** for database integrity.

## Critical Findings

### Field Population Rates (Event Links, OwnerType=2)

Analysis of 11,775 citation links to events in production database:

| Field | Population Rate | Status | Notes |
|-------|----------------|--------|-------|
| **Quality** | **99.8%** | **CRITICAL** | Schema says "Not Implemented" but 99.8% have values |
| **IsPrivate** | **99.8%** | **CRITICAL** | Schema says "Not Implemented" but 99.8% have values |
| **Flags** | **99.8%** | **CRITICAL** | Schema says "Not Implemented" but 99.8% have values |
| SortOrder | 47.1% | Optional | NULL (legacy) or 0 (new records) |
| UTCModDate | 47.1% | Recommended | Timestamp for modification tracking |

### Schema Documentation vs Reality

The schema reference (`schema-reference.md`) states:
- **IsPrivate**: "Not Implemented (e.g., 0.0)"
- **Flags**: "Not Implemented (e.g., 0.0)"
- **SortOrder**: "Not Implemented: Null = Legacy data, 0 = New table entry"

**Reality**: These fields ARE implemented and must be populated to match RootsMagic conventions.

## Required Fields for Citation Links

### Minimum Required (Will fail if missing)

```python
CitationID    # FK to CitationTable
OwnerType     # 0=Person, 1=Family, 2=Event, 7=Name
OwnerID       # FK to owner table based on OwnerType
```

### Critical for Integrity (99.8% populated)

```python
Quality       # 3-character quality indicator
IsPrivate     # 0 or 1 (privacy flag)
Flags         # Integer flags (typically 0)
```

### Recommended for Consistency

```python
SortOrder     # 0 for new records, NULL for legacy
UTCModDate    # Current timestamp
```

## Standard Values by Use Case

### Find a Grave Citation Links

**Observed patterns in existing Find a Grave records:**

```python
Quality = '~~~'  # Most common (unknown quality)
Quality = 'SDX'  # Secondary, Direct, Don't know originality
IsPrivate = 0    # Not private
Flags = 0        # No special flags
SortOrder = 0    # New record (or NULL for legacy)
UTCModDate = <current_timestamp>
```

**Complete INSERT statement:**

```python
cursor.execute("""
    INSERT INTO CitationLinkTable (
        CitationID,
        OwnerType,
        OwnerID,
        SortOrder,
        Quality,
        IsPrivate,
        Flags,
        UTCModDate
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", (
    citation_id,
    2,              # OwnerType=2 for Event
    event_id,
    0,              # SortOrder
    '~~~',          # Quality (Find a Grave default)
    0,              # IsPrivate
    0,              # Flags
    utc_mod_date,   # Current timestamp
))
```

## Quality Field Values

The `Quality` field is a 3-character string indicating source quality:

**Format**: `[Info Type][Derivation][Originality]`

**Character 1 - Information Type:**
- `P` = Primary
- `S` = Secondary
- `~` = Don't know

**Character 2 - Derivation:**
- `D` = Direct
- `I` = Indirect
- `N` = Negative evidence
- `~` = Don't know

**Character 3 - Originality:**
- `O` = Original
- `X` = Derivative
- `~` = Don't know

**Common Values in Production Data:**
- `~~~` = All unknown (most common for Find a Grave)
- `SDX` = Secondary, Direct, Derivative
- `~~S` = Unknown type, Unknown derivation, Secondary originality
- `S~~` = Secondary, Unknown derivation, Unknown originality
- `~D~` = Unknown type, Direct, Unknown originality
- `~DX` = Unknown type, Direct, Derivative
- `SD~` = Secondary, Direct, Unknown originality
- `S~X` = Secondary, Unknown derivation, Derivative
- `D~X` = Direct, Unknown derivation, Derivative
- `S~S` = Secondary, Unknown derivation, Secondary originality

**Recommendation**: Use `'~~~'` for Find a Grave sources unless you have specific quality information.

## OwnerType Values

Citation links can be attached to different record types:

| OwnerType | Links To | Table | Use Case |
|-----------|----------|-------|----------|
| 0 | Person | PersonTable | Direct citation to person |
| 1 | Family | FamilyTable | Citation to family relationship |
| 2 | Event | EventTable | **Most common** - citation to fact/event |
| 6 | Task | TaskTable | Citation to research task |
| 7 | Name | NameTable | Citation to name variant |
| 19 | Association | (Unknown) | Association link |

**Distribution in production database:**
- Event (OwnerType=2): 11,775 links (95.7%)
- Person (OwnerType=0): 407 links (3.3%)
- Name (OwnerType=7): 72 links (0.6%)
- Family (OwnerType=1): 44 links (0.4%)
- Unknown (19): 1 link (0.01%)

**Best Practice**: For burial events, use OwnerType=2 (Event).

## Common Mistakes

### ❌ Missing Quality, IsPrivate, Flags

```python
# WRONG - Missing critical fields
cursor.execute("""
    INSERT INTO CitationLinkTable (
        CitationID, OwnerType, OwnerID
    ) VALUES (?, ?, ?)
""", (citation_id, 2, event_id))
```

**Impact**: Only 0.2% of existing records have these as NULL. Missing these fields creates inconsistent data that may cause RootsMagic UI issues.

### ❌ Incorrect Field Order

```python
# WRONG - Field order matters
cursor.execute("""
    INSERT INTO CitationLinkTable (
        OwnerType, OwnerID, CitationID  # CitationID should be first
    ) VALUES (?, ?, ?)
""", (2, event_id, citation_id))
```

**Best Practice**: Always use named fields in INSERT statements (as shown in correct examples above).

### ❌ Using NULL for Integer Fields

```python
# WRONG - NULL for IsPrivate/Flags
Quality = None      # Should be '~~~'
IsPrivate = None    # Should be 0
Flags = None        # Should be 0
```

**Impact**: 99.8% of records have these populated. NULL values are non-standard.

## Testing Citation Links

### Comparison-Based Testing Pattern

Always compare created citation links with existing records:

```python
def test_citation_link_matches_existing(db_connection):
    """Verify created link matches existing RootsMagic patterns."""
    cursor = db_connection.cursor()

    # Get existing Find a Grave citation link
    cursor.execute("""
        SELECT Quality, IsPrivate, Flags, SortOrder
        FROM CitationLinkTable cl
        JOIN CitationTable c ON cl.CitationID = c.CitationID
        JOIN SourceTable s ON c.SourceID = s.SourceID
        WHERE s.Name LIKE '%Find%Grave%'
        AND cl.OwnerType = 2
        LIMIT 1
    """)
    existing = cursor.fetchone()

    # Create test link
    # ... (your creation code)

    # Fetch created link
    cursor.execute("""
        SELECT Quality, IsPrivate, Flags, SortOrder
        FROM CitationLinkTable
        WHERE CitationID = ?
    """, (citation_id,))
    created = cursor.fetchone()

    # Compare field-by-field
    assert created[0] is not None, "Quality should not be NULL"
    assert created[1] == 0, "IsPrivate should be 0"
    assert created[2] == 0, "Flags should be 0"
    assert created[3] in (0, None), "SortOrder should be 0 or NULL"
```

### Field Population Test

```python
def test_critical_fields_populated(db_connection):
    """Verify critical fields are populated in >99% of records."""
    cursor = db_connection.cursor()

    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN Quality IS NOT NULL THEN 1 ELSE 0 END) as has_quality,
            SUM(CASE WHEN IsPrivate IS NOT NULL THEN 1 ELSE 0 END) as has_isprivate,
            SUM(CASE WHEN Flags IS NOT NULL THEN 1 ELSE 0 END) as has_flags
        FROM CitationLinkTable
        WHERE OwnerType = 2
    """)
    total, has_quality, has_isprivate, has_flags = cursor.fetchone()

    assert (has_quality / total) > 0.99, "Quality should be >99% populated"
    assert (has_isprivate / total) > 0.99, "IsPrivate should be >99% populated"
    assert (has_flags / total) > 0.99, "Flags should be >99% populated"
```

## Reference Implementation

See `src/rmcitecraft/database/findagrave_queries.py` for complete implementation:

- **Line 618**: Link citation to existing burial event
- **Line 920**: Link citation to new burial event
- **Line 1023**: Link citation to parent family
- **Line 1136**: Link citation to spouse family

See `tests/unit/test_database_integrity.py` for comprehensive tests:

- `TestCitationLinkTableIntegrity` class (4 tests)
- Validates schema, field population, and created links

## Migration Guide

If you have existing code that creates citation links without these fields:

### Before
```python
cursor.execute("""
    INSERT INTO CitationLinkTable (
        CitationID, OwnerType, OwnerID, SortOrder, UTCModDate
    ) VALUES (?, ?, ?, ?, ?)
""", (citation_id, 2, event_id, 0, utc_mod_date))
```

### After
```python
cursor.execute("""
    INSERT INTO CitationLinkTable (
        CitationID, OwnerType, OwnerID, SortOrder,
        Quality, IsPrivate, Flags, UTCModDate
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", (
    citation_id, 2, event_id, 0,
    '~~~', 0, 0, utc_mod_date
))
```

### Fixing Existing Records

```python
# Find citation links missing critical fields
cursor.execute("""
    SELECT LinkID FROM CitationLinkTable
    WHERE Quality IS NULL
    OR IsPrivate IS NULL
    OR Flags IS NULL
""")

# Update each record
for (link_id,) in cursor.fetchall():
    cursor.execute("""
        UPDATE CitationLinkTable
        SET Quality = COALESCE(Quality, '~~~'),
            IsPrivate = COALESCE(IsPrivate, 0),
            Flags = COALESCE(Flags, 0)
        WHERE LinkID = ?
    """, (link_id,))
```

## Summary

**Key Takeaways:**
1. **Always populate Quality, IsPrivate, Flags** - 99.8% of existing records have these
2. **Use `'~~~'` for Quality** when source quality is unknown
3. **Use `0` for IsPrivate and Flags** for public records
4. **Use OwnerType=2** for event citations (most common)
5. **Test by comparison** with existing records, not just schema validation

**Remember**: Schema documentation may be outdated. Empirical analysis of production databases reveals the true requirements for database integrity.

---

**Last Updated**: 2025-11-17
**Analysis Based On**: RMCitecraft production database (11,775 event citation links)
**Reference**: `tests/unit/test_database_integrity.py` - TestCitationLinkTableIntegrity
