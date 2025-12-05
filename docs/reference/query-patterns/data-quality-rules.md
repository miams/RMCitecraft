---
priority: reference
topics: [database, census, citation, batch, findagrave]
---

# RootsMagic 11: Data Quality Validation Rules

**Document Version:** 1.0
**Last Updated:** 2025-01-08
**Purpose:** Define systematic validation rules for detecting data quality issues in RootsMagic databases

---

## Overview

This document provides comprehensive validation rules for identifying data quality issues in RootsMagic databases. These rules help AI agents and data analysts detect:

- **Incomplete records** - Missing required fields
- **Logical inconsistencies** - Events in impossible orders (death before birth)
- **Orphaned records** - References to non-existent entities
- **Unsourced facts** - Claims without supporting citations
- **Invalid values** - Data outside acceptable ranges

---

## Validation Categories

### 1. Required Field Combinations
### 2. Logical Consistency Rules
### 3. Referential Integrity
### 4. Source Documentation Quality
### 5. Date Validity
### 6. Value Range Constraints

---

## 1. Required Field Combinations

### Rule 1.1: Every Person Must Have a Primary Name

**Severity:** CRITICAL

**Check:**
```sql
SELECT p.PersonID, p.Sex
FROM PersonTable p
LEFT JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
WHERE n.NameID IS NULL
```

**Expected:** 0 records
**Remediation:** Add primary name or mark person as placeholder

---

### Rule 1.2: Primary Names Should Have Surname OR Given Name

**Severity:** HIGH

**Check:**
```sql
SELECT n.NameID, n.OwnerID, n.Surname, n.Given
FROM NameTable n
WHERE n.IsPrimary = 1
  AND (n.Surname IS NULL OR n.Surname = '')
  AND (n.Given IS NULL OR n.Given = '')
```

**Typical Rate:** <2% acceptable (for unknown individuals)
**Remediation:** Research to find missing name components, or use "[Unknown]" placeholder

---

### Rule 1.3: Birth Events Should Have a Date or Place

**Severity:** MEDIUM

**Check:**
```sql
SELECT e.EventID, e.OwnerID
FROM EventTable e
WHERE e.EventType = 1  -- Birth
  AND (e.Date IS NULL OR e.Date = '' OR e.Date = '.')
  AND (e.PlaceID = 0 OR e.PlaceID IS NULL)
```

**Typical Rate:** 10-15% acceptable
**Remediation:** Research vital records, census data for birth information

---

### Rule 1.4: Death Events Should Have a Date

**Severity:** HIGH

**Check:**
```sql
SELECT e.EventID, e.OwnerID, p.PersonID, n.Surname, n.Given
FROM EventTable e
JOIN PersonTable p ON e.OwnerID = p.PersonID
JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
WHERE e.EventType = 2  -- Death
  AND (e.Date IS NULL OR e.Date = '' OR e.Date = '.')
```

**Typical Rate:** <1% acceptable (very recent deaths may lack dates)
**Remediation:** Check death certificates, obituaries, cemetery records

---

### Rule 1.5: Citations Should Have Page or Detail Information

**Severity:** MEDIUM

**Check (Python):**
```python
import xml.etree.ElementTree as ET

def check_empty_citations(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT CitationID, SourceID, Fields FROM CitationTable")

    empty_citations = []
    for cit_id, src_id, blob in cursor.fetchall():
        if blob:
            xml = blob.decode('utf-8-sig')
            root = ET.fromstring(xml)
            fields = root.findall('.//Field')

            # Check if all field values are empty
            all_empty = all(
                (f.find('Value').text or '').strip() == ''
                for f in fields
            )
            if all_empty:
                empty_citations.append((cit_id, src_id))

    return empty_citations
```

**Remediation:** Add page numbers, URLs, or other citation details

---

## 2. Logical Consistency Rules

### Rule 2.1: Death Must Occur After Birth

**Severity:** CRITICAL

**Check:**
```sql
SELECT
    p.PersonID,
    n.Surname || ', ' || n.Given as Name,
    birth.Date as BirthDate,
    birth.SortDate as BirthSort,
    death.Date as DeathDate,
    death.SortDate as DeathSort
FROM PersonTable p
JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
LEFT JOIN EventTable birth ON p.PersonID = birth.OwnerID AND birth.EventType = 1
LEFT JOIN EventTable death ON p.PersonID = death.OwnerID AND death.EventType = 2
WHERE birth.SortDate IS NOT NULL
  AND death.SortDate IS NOT NULL
  AND birth.SortDate != 9223372036854775807  -- Not "unknown" date
  AND death.SortDate != 9223372036854775807
  AND death.SortDate < birth.SortDate
```

**Expected:** 0 records
**Note:** SortDate value `9223372036854775807` indicates unknown/missing date
**Remediation:** Verify dates, check for data entry errors

---

### Rule 2.2: Child Must Be Born After Parent

**Severity:** CRITICAL

**Check:**
```sql
SELECT
    child.PersonID as ChildID,
    cn.Surname || ', ' || cn.Given as ChildName,
    cb.Date as ChildBirth,
    parent.PersonID as ParentID,
    pn.Surname || ', ' || pn.Given as ParentName,
    pb.Date as ParentBirth
FROM ChildTable ct
JOIN FamilyTable f ON ct.FamilyID = f.FamilyID
JOIN PersonTable child ON ct.ChildID = child.PersonID
JOIN NameTable cn ON child.PersonID = cn.OwnerID AND cn.IsPrimary = 1
LEFT JOIN EventTable cb ON child.PersonID = cb.OwnerID AND cb.EventType = 1
JOIN PersonTable parent ON (f.FatherID = parent.PersonID OR f.MotherID = parent.PersonID)
JOIN NameTable pn ON parent.PersonID = pn.OwnerID AND pn.IsPrimary = 1
LEFT JOIN EventTable pb ON parent.PersonID = pb.OwnerID AND pb.EventType = 1
WHERE cb.SortDate IS NOT NULL
  AND pb.SortDate IS NOT NULL
  AND cb.SortDate != 9223372036854775807
  AND pb.SortDate != 9223372036854775807
  AND cb.SortDate < pb.SortDate
```

**Expected:** 0 records
**Remediation:** Verify parent-child relationships, check for adoption/step-relationships

---

### Rule 2.3: Parent Should Be 12-65 Years Old at Child's Birth

**Severity:** MEDIUM (for <12 or >65), HIGH (for <10 or >70)

**Check:**
```sql
SELECT
    parent.PersonID,
    pn.Surname || ', ' || pn.Given as ParentName,
    parent.Sex,
    pb.Date as ParentBirth,
    cb.Date as ChildBirth,
    CAST((cb.SortDate - pb.SortDate) / 10000000000000 AS INTEGER) as AgeAtBirth
FROM ChildTable ct
JOIN FamilyTable f ON ct.FamilyID = f.FamilyID
JOIN PersonTable child ON ct.ChildID = child.PersonID
LEFT JOIN EventTable cb ON child.PersonID = cb.OwnerID AND cb.EventType = 1
JOIN PersonTable parent ON (f.FatherID = parent.PersonID OR f.MotherID = parent.PersonID)
JOIN NameTable pn ON parent.PersonID = pn.OwnerID AND pn.IsPrimary = 1
LEFT JOIN EventTable pb ON parent.PersonID = pb.OwnerID AND pb.EventType = 1
WHERE cb.SortDate IS NOT NULL
  AND pb.SortDate IS NOT NULL
  AND cb.SortDate != 9223372036854775807
  AND pb.SortDate != 9223372036854775807
  AND (
    (cb.SortDate - pb.SortDate) < 120000000000000  -- < 12 years
    OR (cb.SortDate - pb.SortDate) > 650000000000000  -- > 65 years
  )
```

**Age Calculation:** SortDate difference / 10000000000000 ≈ years
**Remediation:** Verify birth dates, check for data entry errors, consider adoption/step-relationships

---

### Rule 2.4: Marriage Should Occur After Birth

**Severity:** HIGH

**Check:**
```sql
SELECT
    p.PersonID,
    n.Surname || ', ' || n.Given as Name,
    birth.Date as BirthDate,
    marriage.Date as MarriageDate
FROM PersonTable p
JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
LEFT JOIN EventTable birth ON p.PersonID = birth.OwnerID AND birth.EventType = 1
LEFT JOIN FamilyTable f ON (p.PersonID = f.FatherID OR p.PersonID = f.MotherID)
LEFT JOIN EventTable marriage ON f.FamilyID = marriage.OwnerID AND marriage.EventType = 300
WHERE birth.SortDate IS NOT NULL
  AND marriage.SortDate IS NOT NULL
  AND birth.SortDate != 9223372036854775807
  AND marriage.SortDate != 9223372036854775807
  AND marriage.SortDate < birth.SortDate
```

**Expected:** 0 records
**Remediation:** Verify dates, check for data entry errors

---

### Rule 2.5: Events Should Not Occur After Death

**Severity:** HIGH (most events), LOW (for Burial, Probate, Will, Obituary)

**Check:**
```sql
SELECT
    p.PersonID,
    n.Surname || ', ' || n.Given as Name,
    death.Date as DeathDate,
    ft.Name as EventType,
    e.Date as EventDate
FROM PersonTable p
JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
JOIN EventTable death ON p.PersonID = death.OwnerID AND death.EventType = 2
JOIN EventTable e ON p.PersonID = e.OwnerID
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
WHERE death.SortDate IS NOT NULL
  AND e.SortDate IS NOT NULL
  AND death.SortDate != 9223372036854775807
  AND e.SortDate != 9223372036854775807
  AND e.EventType != 2  -- Not the death event itself
  AND e.EventType NOT IN (4, 19, 20, 1000, 1022)  -- Exclude: Burial, Probate, Will, Obituary, News
  AND e.SortDate > death.SortDate
```

**Events Allowed After Death:** Burial, Probate, Will, Obituary, News articles
**Remediation:** Verify event dates, move posthumous events to appropriate fact types

---

### Rule 2.6: Couple Should Not Have Children Before Marriage

**Severity:** LOW (common before modern era)

**Check:**
```sql
SELECT
    f.FamilyID,
    father.Surname || ', ' || father.Given as Father,
    mother.Surname || ', ' || mother.Given as Mother,
    marriage.Date as MarriageDate,
    child.Surname || ', ' || child.Given as FirstChild,
    firstborn.Date as FirstChildBirth
FROM FamilyTable f
JOIN NameTable father ON f.FatherID = father.OwnerID AND father.IsPrimary = 1
JOIN NameTable mother ON f.MotherID = mother.OwnerID AND mother.IsPrimary = 1
LEFT JOIN EventTable marriage ON f.FamilyID = marriage.OwnerID AND marriage.EventType = 300
JOIN ChildTable ct ON f.FamilyID = ct.FamilyID
JOIN PersonTable cp ON ct.ChildID = cp.PersonID
JOIN NameTable child ON cp.PersonID = child.OwnerID AND child.IsPrimary = 1
LEFT JOIN EventTable firstborn ON cp.PersonID = firstborn.OwnerID AND firstborn.EventType = 1
WHERE marriage.SortDate IS NOT NULL
  AND firstborn.SortDate IS NOT NULL
  AND marriage.SortDate != 9223372036854775807
  AND firstborn.SortDate != 9223372036854775807
  AND firstborn.SortDate < marriage.SortDate
ORDER BY f.FamilyID, firstborn.SortDate
```

**Note:** Historical context matters - common law marriages, prior relationships
**Remediation:** Verify marriage date, consider multiple marriages

---

## 3. Referential Integrity

### Rule 3.1: Citations Must Reference Valid Sources

**Severity:** CRITICAL

**Check:**
```sql
SELECT c.CitationID, c.SourceID, c.CitationName
FROM CitationTable c
LEFT JOIN SourceTable s ON c.SourceID = s.SourceID
WHERE s.SourceID IS NULL
```

**Expected:** 0 records
**Remediation:** Delete orphaned citations or restore missing sources

---

### Rule 3.2: Events Must Reference Valid Persons or Families

**Severity:** CRITICAL

**Check:**
```sql
-- Person events
SELECT e.EventID, e.OwnerType, e.OwnerID
FROM EventTable e
WHERE e.OwnerType = 0  -- Person
  AND NOT EXISTS (SELECT 1 FROM PersonTable p WHERE p.PersonID = e.OwnerID)

UNION

-- Family events
SELECT e.EventID, e.OwnerType, e.OwnerID
FROM EventTable e
WHERE e.OwnerType = 1  -- Family
  AND NOT EXISTS (SELECT 1 FROM FamilyTable f WHERE f.FamilyID = e.OwnerID)
```

**Expected:** 0 records
**Remediation:** Delete orphaned events or restore missing persons/families

---

### Rule 3.3: ChildTable Must Reference Valid Families and Persons

**Severity:** CRITICAL

**Check:**
```sql
SELECT ct.ChildID, ct.FamilyID
FROM ChildTable ct
LEFT JOIN PersonTable p ON ct.ChildID = p.PersonID
LEFT JOIN FamilyTable f ON ct.FamilyID = f.FamilyID
WHERE p.PersonID IS NULL OR f.FamilyID IS NULL
```

**Expected:** 0 records
**Remediation:** Delete orphaned relationships or restore missing persons/families

---

### Rule 3.4: Events Should Reference Valid PlaceIDs

**Severity:** MEDIUM

**Check:**
```sql
SELECT e.EventID, e.OwnerID, e.PlaceID
FROM EventTable e
WHERE e.PlaceID > 0
  AND NOT EXISTS (SELECT 1 FROM PlaceTable p WHERE p.PlaceID = e.PlaceID)
```

**Expected:** 0 records
**Remediation:** Restore missing places or reset PlaceID to 0

---

## 4. Source Documentation Quality

### Rule 4.1: Vital Events Should Be Sourced

**Severity:** HIGH

**Check:**
```sql
SELECT
    ft.Name as EventType,
    COUNT(DISTINCT e.EventID) as TotalEvents,
    COUNT(DISTINCT cl.LinkID) as SourcedEvents,
    COUNT(DISTINCT e.EventID) - COUNT(DISTINCT cl.LinkID) as UnsourcedEvents
FROM EventTable e
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
LEFT JOIN CitationLinkTable cl ON e.EventID = cl.OwnerID AND cl.OwnerType = 2
WHERE e.EventType IN (1, 2, 3, 4, 300)  -- Birth, Death, Christen, Burial, Marriage
GROUP BY ft.FactTypeID, ft.Name
HAVING COUNT(DISTINCT e.EventID) > 0
ORDER BY (COUNT(DISTINCT e.EventID) - COUNT(DISTINCT cl.LinkID)) DESC
```

**Acceptable Rate:** <20% unsourced for vital events
**Sample Data:**
- Birth: 83% unsourced
- Death: 74% unsourced
- Marriage: 82% unsourced

**Remediation:** Research and add citations from vital records, certificates, church records

---

### Rule 4.2: Sources Should Have Citations

**Severity:** LOW

**Check:**
```sql
SELECT s.SourceID, s.Name
FROM SourceTable s
LEFT JOIN CitationTable c ON s.SourceID = c.SourceID
WHERE c.CitationID IS NULL
```

**Note:** Unused sources may be placeholders for future research
**Remediation:** Delete unused sources or create citations linking them to facts

---

### Rule 4.3: Template-Based Sources Should Have Complete Metadata

**Severity:** MEDIUM

**Check (Python):**
```python
def check_incomplete_sources(conn):
    cursor = conn.cursor()

    # Get template field definitions
    cursor.execute("""
        SELECT s.SourceID, s.Name, s.TemplateID, s.Fields, st.FieldDefs
        FROM SourceTable s
        JOIN SourceTemplateTable st ON s.TemplateID = st.TemplateID
        WHERE s.TemplateID > 0
    """)

    incomplete = []
    for src_id, name, tmpl_id, src_blob, tmpl_blob in cursor.fetchall():
        # Parse template to get required source-level fields
        tmpl_xml = tmpl_blob.decode('utf-8-sig')
        tmpl_root = ET.fromstring(tmpl_xml)

        required_fields = [
            field.find('FieldName').text
            for field in tmpl_root.findall('.//Field')
            if field.find('CitationField').text == 'False'
        ]

        # Parse source BLOB to get actual fields
        src_xml = src_blob.decode('utf-8-sig')
        src_root = ET.fromstring(src_xml)

        actual_fields = {
            field.find('Name').text: field.find('Value').text or ''
            for field in src_root.findall('.//Field')
        }

        # Check for missing or empty required fields
        missing = [
            f for f in required_fields
            if f not in actual_fields or not actual_fields[f].strip()
        ]

        if missing:
            incomplete.append((src_id, name, missing))

    return incomplete
```

**Remediation:** Fill in missing source metadata (author, title, publisher, dates)

---

## 5. Date Validity

### Rule 5.1: SortDate Should Match Encoded Date

**Severity:** MEDIUM

**Check:** Compare Date field encoding with SortDate value
**Implementation:** Parse Date field per RM11_Date_Format.md and verify SortDate

---

### Rule 5.2: Dates Should Be Within Historical Range

**Severity:** HIGH

**Check:**
```sql
SELECT e.EventID, e.OwnerID, ft.Name, e.Date, e.SortDate
FROM EventTable e
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
WHERE e.SortDate IS NOT NULL
  AND e.SortDate != 9223372036854775807  -- Unknown date marker
  AND (
    -- Before year 1000 AD (unlikely for most genealogy)
    e.SortDate < 5000000000000000000
    -- After current year + 1
    OR e.SortDate > 6800000000000000000
  )
```

**Note:** Adjust ranges based on your research period
**Remediation:** Verify dates, check for data entry errors

---

### Rule 5.3: Birth and Death Dates Should Imply Reasonable Lifespan

**Severity:** MEDIUM

**Check:**
```sql
SELECT
    p.PersonID,
    n.Surname || ', ' || n.Given as Name,
    birth.Date as BirthDate,
    death.Date as DeathDate,
    CAST((death.SortDate - birth.SortDate) / 10000000000000 AS INTEGER) as Lifespan
FROM PersonTable p
JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
JOIN EventTable birth ON p.PersonID = birth.OwnerID AND birth.EventType = 1
JOIN EventTable death ON p.PersonID = death.OwnerID AND death.EventType = 2
WHERE birth.SortDate IS NOT NULL
  AND death.SortDate IS NOT NULL
  AND birth.SortDate != 9223372036854775807
  AND death.SortDate != 9223372036854775807
  AND (
    (death.SortDate - birth.SortDate) < 0  -- Negative lifespan
    OR (death.SortDate - birth.SortDate) > 1200000000000000  -- > 120 years
  )
```

**Acceptable Range:** 0-120 years (rare exceptions for longevity)
**Remediation:** Verify both dates, check for data entry errors

---

## 6. Value Range Constraints

### Rule 6.1: PersonTable.Sex Should Be 0, 1, or 2

**Severity:** MEDIUM

**Check:**
```sql
SELECT PersonID, Sex
FROM PersonTable
WHERE Sex NOT IN (0, 1, 2)
```

**Values:** 0=Male, 1=Female, 2=Unknown
**Expected:** 0 records
**Remediation:** Correct invalid sex values

---

### Rule 6.2: Proof Field Should Be 0-3

**Severity:** LOW

**Check:**
```sql
SELECT EventID, Proof
FROM EventTable
WHERE Proof NOT IN (0, 1, 2, 3)
```

**Values:** 0=Blank, 1=Proven, 2=Disproven, 3=Disputed
**Expected:** 0 records
**Remediation:** Correct invalid proof values

---

### Rule 6.3: IsPrimary Should Be 0 or 1

**Severity:** MEDIUM

**Check:**
```sql
SELECT NameID, IsPrimary
FROM NameTable
WHERE IsPrimary NOT IN (0, 1)
```

**Expected:** 0 records
**Remediation:** Correct invalid boolean values

---

### Rule 6.4: Each Person Should Have Exactly One Primary Name

**Severity:** HIGH

**Check:**
```sql
SELECT OwnerID, COUNT(*) as PrimaryNameCount
FROM NameTable
WHERE IsPrimary = 1
GROUP BY OwnerID
HAVING COUNT(*) != 1
```

**Expected:** 0 records
**Remediation:** Designate exactly one name as primary per person

---

## Data Quality Severity Levels

| Severity | Impact | Action Required |
|----------|--------|-----------------|
| **CRITICAL** | Database integrity violated | Fix immediately |
| **HIGH** | Significant genealogical error | Investigate and correct |
| **MEDIUM** | Possible error or incomplete data | Review when time permits |
| **LOW** | Minor issue or style preference | Optional improvement |

---

## Summary Report Template

### Python: Generate Data Quality Report

```python
def generate_quality_report(db_path):
    """Generate comprehensive data quality report."""
    conn = connect_rmtree(db_path)

    report = {
        'database': db_path,
        'generated': datetime.now(),
        'issues': {
            'critical': [],
            'high': [],
            'medium': [],
            'low': []
        },
        'summary': {}
    }

    # Run all validation rules
    # Rule 1.1: People without names
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*)
        FROM PersonTable p
        LEFT JOIN NameTable n ON p.PersonID = n.OwnerID AND n.IsPrimary = 1
        WHERE n.NameID IS NULL
    """)
    count = cursor.fetchone()[0]
    if count > 0:
        report['issues']['critical'].append({
            'rule': '1.1',
            'name': 'People without primary names',
            'count': count
        })

    # Rule 2.1: Death before birth
    cursor.execute("""
        SELECT COUNT(*)
        FROM PersonTable p
        JOIN EventTable birth ON p.PersonID = birth.OwnerID AND birth.EventType = 1
        JOIN EventTable death ON p.PersonID = death.OwnerID AND death.EventType = 2
        WHERE birth.SortDate != 9223372036854775807
          AND death.SortDate != 9223372036854775807
          AND death.SortDate < birth.SortDate
    """)
    count = cursor.fetchone()[0]
    if count > 0:
        report['issues']['critical'].append({
            'rule': '2.1',
            'name': 'Death before birth',
            'count': count
        })

    # ... more rules ...

    # Summary statistics
    report['summary'] = {
        'total_people': get_count(cursor, 'PersonTable'),
        'total_events': get_count(cursor, 'EventTable'),
        'total_sources': get_count(cursor, 'SourceTable'),
        'total_citations': get_count(cursor, 'CitationTable'),
        'critical_issues': len(report['issues']['critical']),
        'high_issues': len(report['issues']['high']),
        'medium_issues': len(report['issues']['medium']),
        'low_issues': len(report['issues']['low'])
    }

    conn.close()
    return report
```

---

## Notes for AI Agents

1. **Unknown Date Marker:** SortDate value `9223372036854775807` indicates missing/unknown date - exclude from date comparisons

2. **Age Calculation:** Approximate years = `(SortDate2 - SortDate1) / 10000000000000`

3. **PlaceID = 0** means no place assigned (not an error, just unknown)

4. **IsPrivate flag** - respect privacy settings when generating reports

5. **Proof levels** - use to assess source quality:
   - 0 = Blank/unknown
   - 1 = Proven (high confidence)
   - 2 = Disproven (contradicts evidence)
   - 3 = Disputed (conflicting evidence)

6. **Multiple issues** - prioritize by severity, fix critical issues first

7. **Historical context** - some "issues" are historically normal (marriage age, children before marriage)

8. **Batch processing** - run all checks periodically, not per-record

---

## Related Documentation

- **RM11_Schema_Reference.md** - Table structures and relationships
- **RM11_Date_Format.md** - Date encoding specification
- **RM11_BLOB_SourceFields.md** - Source metadata extraction
- **RM11_BLOB_CitationFields.md** - Citation detail extraction

---

**End of Document**
