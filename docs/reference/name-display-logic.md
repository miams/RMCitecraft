---
priority: reference
topics: [database, citation, ui]
---

# RootsMagic 11: Name Display Logic

**Document Version:** 1.0
**Last Updated:** 2025-01-08
**Related Tables:** NameTable, PersonTable
**Purpose:** Rules for selecting and displaying person names

---

## Overview

RootsMagic stores multiple names per person (birth names, married names, alternate spellings, nicknames). This document defines the logic for selecting which name to display in different contexts.

### Key Statistics

- **Average names per person:** 1.04
- **Persons with multiple names:** 517 (4.5%)
- **Maximum names for one person:** 5
- **Primary names:** 11,571 (one per person)
- **Alternate names:** 517

---

## IsPrimary Flag

**Purpose:** Designate one name as the "primary" or "preferred" name for a person.

### Rules

1. **Every person must have exactly one primary name** (IsPrimary = 1)
2. **All other names are alternates** (IsPrimary = 0)
3. **Primary name is used by default** in most contexts

### Query Primary Name

```sql
SELECT Surname, Given, Prefix, Suffix, Nickname
FROM NameTable
WHERE OwnerID = ?  -- PersonID
  AND IsPrimary = 1;
```

---

## NameType Values

The `NameType` field categorizes name purposes:

| NameType | Count | Meaning | Usage |
|----------|-------|---------|-------|
| 0 | 12,045 | Birth/Standard name | Default (99.6%) |
| 1 | 8 | Also Known As (AKA) | Alternate identity |
| 5 | 18 | Married name | Post-marriage |
| 6 | 7 | Immigrant name | Pre-immigration |
| 7 | 10 | Maiden name | Pre-marriage surname |

**Note:** NameType=0 is used for 99.6% of all names (both primary and alternate).

---

## Name Selection Rules

### Rule 1: Default Display (Most Contexts)

**Use the primary name:**

```sql
SELECT n.Surname, n.Given
FROM PersonTable p
JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
WHERE p.PersonID = ?;
```

**Used for:**
- Person lists
- Index entries
- Default biography text
- Report headers

---

### Rule 2: Context-Specific Display

**Marriage events - use maiden name if available:**

```sql
-- For bride, show maiden name (NameType=7) if exists
SELECT COALESCE(
    (SELECT Surname FROM NameTable WHERE OwnerID = ? AND NameType = 7),
    (SELECT Surname FROM NameTable WHERE OwnerID = ? AND IsPrimary = 1)
) as DisplaySurname;
```

**Post-marriage events - use married name:**

```sql
-- After marriage date, show married name (NameType=5) if exists
SELECT COALESCE(
    (SELECT Surname FROM NameTable WHERE OwnerID = ? AND NameType = 5),
    (SELECT Surname FROM NameTable WHERE OwnerID = ? AND IsPrimary = 1)
) as DisplaySurname;
```

---

### Rule 3: Show All Names (Comprehensive View)

**List all names for a person:**

```sql
SELECT
    IsPrimary,
    NameType,
    Surname,
    Given,
    Prefix,
    Suffix,
    Nickname
FROM NameTable
WHERE OwnerID = ?
ORDER BY IsPrimary DESC, NameType;
```

**Display format:**
- Primary: **John Smith**
- Also known as: John J. Smith
- Married name: Jane Smith (née Jones)
- Immigrant name: Johann Schmidt

---

## Name Component Fields

### Standard Components

| Field | Description | Example |
|-------|-------------|---------|
| **Surname** | Last name / family name | Smith |
| **Given** | First and middle names | John William |
| **Prefix** | Title before name | Dr., Rev., Sir |
| **Suffix** | Designation after name | Jr., III, Esq. |
| **Nickname** | Informal name | Jack, Johnny |

### Full Name Construction

```python
def format_full_name(name_record, include_nickname=False):
    """
    Construct full name from components.

    Args:
        name_record: Dict with name fields
        include_nickname: Include nickname in parentheses

    Returns:
        str: Formatted full name
    """
    parts = []

    # Prefix (Dr., Rev.)
    if name_record.get('prefix'):
        parts.append(name_record['prefix'])

    # Given name(s)
    if name_record.get('given'):
        parts.append(name_record['given'])

    # Surname
    if name_record.get('surname'):
        parts.append(name_record['surname'])

    # Suffix (Jr., III)
    if name_record.get('suffix'):
        parts.append(name_record['suffix'])

    full_name = ' '.join(parts)

    # Nickname
    if include_nickname and name_record.get('nickname'):
        full_name += f' ("{name_record["nickname"]}")'

    return full_name

# Example:
# Prefix: Dr.
# Given: John William
# Surname: Smith
# Suffix: Jr.
# Nickname: Jack
# Output: "Dr. John William Smith Jr. (Jack)"
```

---

## Display Field (Future Use)

**Status:** Currently unused in RM11

The `Display` field exists but contains only "0" values in current databases.

**Intended Purpose:** (Speculation based on field name)
- May be used in future versions to control name display preferences
- Could indicate display order or visibility settings

**Current Recommendation:** Ignore this field

---

## Multiple Name Scenarios

### Scenario 1: Spelling Variations

**Person:** James Fredrick Tittsworth
**Names:**
1. James Fredrick Tittsworth (Primary)
2. Fred Tittsworth (Alternate)
3. James F. Titsworth (Alternate)
4. James Fred Tittsworth (Alternate)
5. James Tittsworth (Alternate)

**Display Logic:**
- Default: Use #1 (Primary)
- When citing sources: Note spelling variation if citation uses alternate
- Biography: Mention "also spelled Titsworth" or "known as Fred"

---

### Scenario 2: Married Name

**Person:** Mary Elizabeth Jones (later Smith)
**Names:**
1. Mary Elizabeth Smith (Primary, NameType=0)
2. Mary Elizabeth Jones (Alternate, NameType=7 - Maiden)

**Display Logic:**
- Default: Use #1 (Primary = married name)
- Pre-marriage events: Use #2 (Maiden name)
- Post-marriage events: Use #1 (Married name)
- Biography: "Mary Elizabeth Jones married John Smith..."

---

### Scenario 3: Immigrant Name Change

**Person:** Johann Schmidt (later John Smith)
**Names:**
1. John Smith (Primary, NameType=0)
2. Johann Schmidt (Alternate, NameType=6 - Immigrant)

**Display Logic:**
- Default: Use #1 (Americanized name)
- Pre-immigration: Use #2
- Post-immigration: Use #1
- Biography: "Johann Schmidt, who later anglicized his name to John Smith..."

---

## Python: Name Selection Functions

### Get Primary Name

```python
def get_primary_name(person_id, conn):
    """Get primary name for a person."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT Surname, Given, Prefix, Suffix, Nickname
        FROM NameTable
        WHERE OwnerID = ? AND IsPrimary = 1
    """, (person_id,))

    result = cursor.fetchone()
    if result:
        return {
            'surname': result[0],
            'given': result[1],
            'prefix': result[2],
            'suffix': result[3],
            'nickname': result[4]
        }

    return None
```

### Get All Names

```python
def get_all_names(person_id, conn):
    """Get all names for a person."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            NameID,
            IsPrimary,
            NameType,
            Surname,
            Given,
            Prefix,
            Suffix,
            Nickname
        FROM NameTable
        WHERE OwnerID = ?
        ORDER BY IsPrimary DESC, NameType
    """, (person_id,))

    names = []
    for row in cursor.fetchall():
        names.append({
            'name_id': row[0],
            'is_primary': row[1] == 1,
            'name_type': row[2],
            'surname': row[3],
            'given': row[4],
            'prefix': row[5],
            'suffix': row[6],
            'nickname': row[7]
        })

    return names
```

### Get Name at Specific Date

```python
def get_name_at_date(person_id, event_date, conn):
    """
    Get appropriate name for a specific date.

    Args:
        person_id: PersonID
        event_date: Date of event (for married name logic)
        conn: Database connection

    Returns:
        dict: Name record appropriate for date
    """
    cursor = conn.cursor()

    # Get marriage date if exists
    cursor.execute("""
        SELECT e.SortDate
        FROM FamilyTable f
        JOIN EventTable e ON f.FamilyID = e.OwnerID AND e.EventType = 300
        WHERE (f.FatherID = ? OR f.MotherID = ?)
        ORDER BY e.SortDate
        LIMIT 1
    """, (person_id, person_id))

    marriage_result = cursor.fetchone()

    # If event is before marriage, prefer maiden name
    if marriage_result:
        marriage_date = marriage_result[0]

        if event_date and event_date < marriage_date:
            # Try to get maiden name
            cursor.execute("""
                SELECT Surname, Given, Prefix, Suffix, Nickname
                FROM NameTable
                WHERE OwnerID = ? AND NameType = 7
            """, (person_id,))

            maiden = cursor.fetchone()
            if maiden:
                return {
                    'surname': maiden[0],
                    'given': maiden[1],
                    'prefix': maiden[2],
                    'suffix': maiden[3],
                    'nickname': maiden[4],
                    'type': 'maiden'
                }

    # Default to primary name
    return get_primary_name(person_id, conn)
```

---

## Biography Display Recommendations

### First Mention

Use full primary name:
> **Dr. John William Smith Jr.** was born...

### Subsequent Mentions

Use given name or surname only:
> John attended school...
> Smith enlisted in the Army...

### Alternate Names

Mention in context:
> Though christened Johann Schmidt, he later Americanized his name to John Smith.
> Mary Elizabeth Jones married John Smith on June 15, 1875.
> Known to friends as "Jack", John William Smith was...

---

## Validation Rules

### Rule 1: Exactly One Primary Name

```sql
-- Check for persons without primary name
SELECT p.PersonID
FROM PersonTable p
LEFT JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
WHERE n.NameID IS NULL;

-- Check for persons with multiple primary names
SELECT OwnerID, COUNT(*) as PrimaryCount
FROM NameTable
WHERE IsPrimary = 1
GROUP BY OwnerID
HAVING COUNT(*) > 1;
```

### Rule 2: Surname or Given Required

```sql
-- Find names missing both surname and given
SELECT NameID, OwnerID
FROM NameTable
WHERE (Surname IS NULL OR Surname = '')
  AND (Given IS NULL OR Given = '');
```

---

## Notes for AI Agents

1. **Always use IsPrimary=1** for default name selection

2. **NameType mostly unused** - 99.6% are NameType=0

3. **Display field is empty** - Ignore this field in RM11

4. **Multiple names are rare** - Only 4.5% of persons

5. **Context matters for married names** - Check event date vs marriage date

6. **Format consistently** - Use full name on first mention, surname thereafter

7. **Alternate spellings** - Note in biography if source uses different spelling

8. **Nickname usage** - Include in parentheses when relevant

9. **Prefix/Suffix** - Include titles (Dr., Jr.) in formal contexts

10. **Validation critical** - Every person must have exactly one primary name

---

## Related Documentation

- **RM11_Schema_Reference.md** - NameTable schema
- **RM11_Biography_Best_Practices.md** - Name usage in narratives
- **RM11_Data_Quality_Rules.md** - Name validation rules

---

## Summary

RootsMagic name display logic is straightforward:

1. **One primary name per person** (IsPrimary=1)
2. **Optional alternate names** (IsPrimary=0)
3. **NameType categorizes purpose** (0=standard, 5=married, 7=maiden)
4. **Context-aware selection** (maiden name pre-marriage, married name after)
5. **Component assembly** (Prefix + Given + Surname + Suffix + Nickname)

For most purposes, **use the primary name**. For biographical accuracy, consider using maiden names for pre-marriage events and noting alternate spellings when they appear in source documents.

---

**End of Document**
