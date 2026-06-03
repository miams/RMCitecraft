# RootsMagic Fact Types Reference

Complete enumeration of built-in RootsMagic event and fact types.

## Event Type Codes (FactTypeTable.FactTypeID)

### Vital Events (Individual - OwnerType=0)

| ID | Name | Abbrev | GEDCOM Tag | UseValue | UseDate | UsePlace |
|----|------|--------|------------|----------|---------|----------|
| 1 | Birth | Birth | BIRT | 0 | 1 | 1 |
| 2 | Death | Death | DEAT | 0 | 1 | 1 |
| 3 | Burial | Burial | BURI | 0 | 1 | 1 |
| 4 | Christening | Chr. | CHR | 0 | 1 | 1 |
| 5 | Cremation | Crem. | CREM | 0 | 1 | 1 |
| 6 | Adoption | Adoption | ADOP | 0 | 1 | 1 |
| 7 | Bar Mitzvah | Bar Mitz. | BARM | 0 | 1 | 1 |
| 8 | Bas Mitzvah | Bas Mitz. | BASM | 0 | 1 | 1 |
| 9 | Blessing | Blessing | BLES | 0 | 1 | 1 |
| 10 | Adult Christening | A. Chr. | CHRA | 0 | 1 | 1 |
| 11 | Confirmation | Confirm. | CONF | 0 | 1 | 1 |
| 12 | First Communion | 1st Com. | FCOM | 0 | 1 | 1 |

### Census (Individual - OwnerType=0)

| ID | Name | Abbrev | GEDCOM Tag | UseValue | UseDate | UsePlace |
|----|------|--------|------------|----------|---------|----------|
| 18 | Census | Census | CENS | 1 | 1 | 1 |

### Residence & Migration (Individual - OwnerType=0)

| ID | Name | Abbrev | GEDCOM Tag | UseValue | UseDate | UsePlace |
|----|------|--------|------------|----------|---------|----------|
| 13 | Emigration | Emigr. | EMIG | 0 | 1 | 1 |
| 14 | Immigration | Immigr. | IMMI | 0 | 1 | 1 |
| 15 | Naturalization | Natural. | NATU | 0 | 1 | 1 |
| 19 | Residence | Residence | RESI | 0 | 1 | 1 |

### Education & Occupation (Individual - OwnerType=0)

| ID | Name | Abbrev | GEDCOM Tag | UseValue | UseDate | UsePlace |
|----|------|--------|------------|----------|---------|----------|
| 17 | Education | Educ. | EDUC | 1 | 1 | 1 |
| 20 | Occupation | Occup. | OCCU | 1 | 1 | 1 |
| 21 | Graduation | Grad. | GRAD | 0 | 1 | 1 |

### Military (Individual - OwnerType=0)

| ID | Name | Abbrev | GEDCOM Tag | UseValue | UseDate | UsePlace |
|----|------|--------|------------|----------|---------|----------|
| 23 | Military Service | Mil. Serv. | _MILT | 1 | 1 | 1 |
| 24 | Military Draft | Draft | _MISR | 1 | 1 | 1 |

### Legal & Financial (Individual - OwnerType=0)

| ID | Name | Abbrev | GEDCOM Tag | UseValue | UseDate | UsePlace |
|----|------|--------|------------|----------|---------|----------|
| 22 | Will | Will | WILL | 0 | 1 | 1 |
| 25 | Probate | Probate | PROB | 0 | 1 | 1 |
| 27 | Retirement | Retire. | RETI | 0 | 1 | 1 |
| 28 | Property | Property | PROP | 1 | 1 | 1 |

### Physical Description (Individual - OwnerType=0)

| ID | Name | Abbrev | GEDCOM Tag | UseValue | UseDate | UsePlace |
|----|------|--------|------------|----------|---------|----------|
| 29 | Physical Description | Descrip. | DSCR | 1 | 1 | 1 |
| 30 | Cause of Death | Cause | CAUS | 1 | 1 | 1 |

### LDS Ordinances (Individual - OwnerType=0)

| ID | Name | Abbrev | GEDCOM Tag | UseValue | UseDate | UsePlace |
|----|------|--------|------------|----------|---------|----------|
| 31 | Baptism (LDS) | Baptism | BAPL | 0 | 1 | 1 |
| 32 | Endowment (LDS) | Endow. | ENDL | 0 | 1 | 1 |
| 33 | Sealed to Parents (LDS) | Sealed | SLGC | 0 | 1 | 1 |

### Family Events (Family - OwnerType=1)

| ID | Name | Abbrev | GEDCOM Tag | UseValue | UseDate | UsePlace |
|----|------|--------|------------|----------|---------|----------|
| 300 | Marriage | Marriage | MARR | 0 | 1 | 1 |
| 301 | Divorce | Divorce | DIV | 0 | 1 | 1 |
| 302 | Annulment | Annul. | ANUL | 0 | 1 | 1 |
| 303 | Marriage Bann | Bann | MARB | 0 | 1 | 1 |
| 304 | Marriage Contract | Marr. Con. | MARC | 0 | 1 | 1 |
| 305 | Marriage License | Marr. Lic. | MARL | 0 | 1 | 1 |
| 306 | Engagement | Engage. | ENGA | 0 | 1 | 1 |
| 307 | Divorce Filed | Div. Filed | DIVF | 0 | 1 | 1 |
| 308 | Marriage Settlement | Marr. Set. | MARS | 0 | 1 | 1 |

### LDS Family Ordinances (Family - OwnerType=1)

| ID | Name | Abbrev | GEDCOM Tag | UseValue | UseDate | UsePlace |
|----|------|--------|------------|----------|---------|----------|
| 309 | Sealed to Spouse (LDS) | Sealed | SLGS | 0 | 1 | 1 |

## Field Usage Flags

### UseValue
- **0** = No description field
- **1** = Has description field (EventTable.Details)

### UseDate
- **0** = No date field
- **1** = Has date field (EventTable.Date)

### UsePlace
- **0** = No place field
- **1** = Has place field (EventTable.PlaceID)

## OwnerType Values

| Value | Type | Description |
|-------|------|-------------|
| 0 | Individual | Event belongs to a person |
| 1 | Family | Event belongs to a couple/family |

## Common Query Patterns

### Find All Events by Type for Person

```sql
SELECT e.EventID, e.Date, e.Details, pl.Name as Place
FROM EventTable e
LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
WHERE e.OwnerID = 1561  -- PersonID
  AND e.OwnerType = 0    -- Individual event
  AND e.EventType = 18   -- Census
ORDER BY e.Date;
```

### Find Marriage Events

**Important:** Marriage events use OwnerType=1 (Family), not Person.

```sql
SELECT e.EventID, e.Date, pl.Name as Place,
       f.FatherID, f.MotherID,
       nf.Given || ' ' || nf.Surname as Spouse1,
       nm.Given || ' ' || nm.Surname as Spouse2
FROM EventTable e
JOIN FamilyTable f ON e.OwnerID = f.FamilyID
LEFT JOIN NameTable nf ON nf.OwnerID = f.FatherID AND nf.IsPrimary = 1
LEFT JOIN NameTable nm ON nm.OwnerID = f.MotherID AND nm.IsPrimary = 1
LEFT JOIN PlaceTable pl ON e.PlaceID = pl.PlaceID
WHERE e.EventType = 300  -- Marriage
  AND e.OwnerType = 1    -- Family event
ORDER BY e.Date;
```

### Count Event Types in Database

```sql
SELECT ft.Name, ft.OwnerType, COUNT(*) as EventCount
FROM EventTable e
JOIN FactTypeTable ft ON e.EventType = ft.FactTypeID
GROUP BY e.EventType, ft.Name, ft.OwnerType
ORDER BY EventCount DESC;
```

## Custom Fact Types

User-defined fact types have FactTypeID >= 1000. They always use:
- **GedcomTag:** `EVEN`
- **Name:** User-defined
- **UseValue/UseDate/UsePlace:** User-configured

```sql
-- Find all custom fact types
SELECT FactTypeID, Name, Abbrev, OwnerType, UseValue, UseDate, UsePlace
FROM FactTypeTable
WHERE FactTypeID >= 1000
ORDER BY Name;
```

## Notes

1. **Census events** (ID 18) are frequently shared via WitnessTable
2. **Marriage events** (ID 300) use FamilyID as OwnerID, not PersonID
3. **LDS ordinances** (IDs 31-33, 309) have special status tracking
4. **UseValue=1** indicates the event can have a Description field
5. **Military Draft** (ID 24) commonly used for WWI/WWII draft registrations
