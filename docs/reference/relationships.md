# RootsMagic 11 Relationship Encoding

This document describes how RootsMagic 11 encodes genealogical relationships using three fields: `Relate1`, `Relate2`, and `Flags`.

## Overview

RootsMagic uses a three-field system to encode relationships between individuals in the genealogical database:

- **Relate1**: Number of generations from Person A to the Most Recent Common Ancestor (MRCA)
- **Relate2**: Number of generations from Person B to the Most Recent Common Ancestor (MRCA)
- **Flags**: Relationship modifier flags (half-relationship, spouse of blood relation, etc.)

These three values work together to precisely describe any genealogical relationship, from direct ancestors/descendants to cousins, in-laws, and complex mixed relationships.

## Field Definitions

### Relate1 Field

Represents the number of generations from **Person A** (the reference person) to the Most Recent Common Ancestor.

- `0` = Person A is the MRCA or there is no blood relation
- `1` = 1 generation up/down from MRCA (parent/child level)
- `2` = 2 generations up/down from MRCA (grandparent/grandchild level)
- `3+` = 3 or more generations from MRCA

### Relate2 Field

Represents the number of generations from **Person B** (the related person) to the Most Recent Common Ancestor.

- `0` = Person B is the MRCA or there is no blood relation
- `1` = 1 generation up/down from MRCA (parent/child level)
- `2` = 2 generations up/down from MRCA (grandparent/grandchild level)
- `3+` = 3 or more generations from MRCA

### Flags Field

Modifies the basic relationship to indicate special cases.

| Flag | Meaning | Description |
|------|---------|-------------|
| `0` | Blood Relation | Direct blood relationship with no modifiers |
| `1` | Half Relationship | Half-sibling relationship (one common parent) |
| `2` | Spouse of Male Blood Relation | Married to a male blood relative (uses Father/Uncle/Cousin terms) |
| `3` | Spouse of Half Male Blood Relation | Married to a male half-blood relative |
| `6` | Spouse of Female Blood Relation | Married to a female blood relative (uses Mother/Aunt/Cousin terms) |
| `7` | Spouse of Half Female Blood Relation | Married to a female half-blood relative |
| `10` | Spouse of Half Blood Relation (Unknown Sex) | Married to a half-blood relative of unknown sex |

## Relationship Calculation Logic

The relationship type is determined by the combination of `Relate1`, `Relate2`, and `Flags`:

### Direct Line Relationships

When one of the Relate values is `0`, the relationship is direct (ancestor or descendant):

- **Relate1 = 0, Relate2 > 0**: Person B is an **ancestor** of Person A
  - Relate2 = 1: Father/Mother
  - Relate2 = 2: Grandfather/Grandmother
  - Relate2 = 3: Great grandfather/Great grandmother
  - Relate2 = 4+: Add "great" prefix for each generation beyond 2

- **Relate1 > 0, Relate2 = 0**: Person B is a **descendant** of Person A
  - Relate1 = 1: Son/Daughter
  - Relate1 = 2: Grandson/Granddaughter
  - Relate1 = 3: Great grandchild
  - Relate1 = 4+: Add "great" prefix for each generation beyond 2

### Collateral Relationships (Siblings, Aunts/Uncles, Cousins)

When both Relate1 and Relate2 are greater than 0, the relationship is collateral:

#### Siblings (Relate1 = 1, Relate2 = 1)
- Flags = 0: Full Brother/Sister
- Flags = 1: Half Brother/Sister

#### Aunt/Uncle - Nephew/Niece Relationships

**Aunts/Uncles** (Relate1 = 1, Relate2 ≥ 2):
- Relate2 = 2: Aunt/Uncle
- Relate2 = 3: Grand Aunt/Uncle
- Relate2 = 4: Great-Grand Aunt/Uncle
- Relate2 = 5+: Add "great" for each generation

**Nephews/Nieces** (Relate1 ≥ 2, Relate2 = 1):
- Relate1 = 2: Nephew/Niece
- Relate1 = 3: Grand Nephew/Niece
- Relate1 = 4+: Add "great" for each generation

#### Cousin Relationships

Cousins are calculated when both Relate1 and Relate2 are ≥ 2:

**Cousin Degree** = MIN(Relate1, Relate2) - 1
- Degree 1 = First cousin
- Degree 2 = Second cousin
- Degree 3 = Third cousin
- etc.

**Times Removed** = ABS(Relate1 - Relate2)
- 0 = Same generation (not removed)
- 1 = Once removed
- 2 = Twice removed
- etc.

**Examples:**
- Relate1 = 2, Relate2 = 2: First cousin (degree 1, removed 0)
- Relate1 = 2, Relate2 = 3: First cousin, once removed (degree 1, removed 1)
- Relate1 = 3, Relate2 = 3: Second cousin (degree 2, removed 0)
- Relate1 = 4, Relate2 = 4: Third cousin (degree 3, removed 0)

### In-Law Relationships

When Flags ≠ 0 and ≠ 1, the relationship is through marriage:

- **Flags = 2**: Spouse of **male** blood relation (terminology uses Father/Uncle/Cousin)
- **Flags = 6**: Spouse of **female** blood relation (terminology uses Mother/Aunt/Cousin)
- **Flags = 3, 7, 10**: Spouse of **half** blood relation (with sex variants)

## Complete Relationship Table

Below is a comprehensive table of relationship encodings found in RootsMagic 11:

| Relate1 | Relate2 | Flags | Relationship | Notes |
|---------|---------|-------|--------------|-------|
| 0.0 | 0.0 | 0.0 | No Blood relation |  |
| 0.0 | 1.0 | 0.0 | Father/Mother | Parents, grandparents, etc. |
| 0.0 | 2.0 | 0.0 | Grandfather/Grandmother |  |
| 0.0 | 3.0 | 0.0 | Great grandfather/Great grandmother |  |
| 0.0 | 4.0 | 0.0 | Second great grandfather/Second great grandmother |  |
| 1.0 | 0.0 | 0.0 | Son/Daughter |  |
| 2.0 | 0.0 | 0.0 | Grandson/Daughter |  |
| 3.0 | 0.0 | 0.0 | Great Grandchild |  |
| 1.0 | 1.0 | 0.0 | Brother/Sister |  |
| 1.0 | 2.0 | 0.0 | Aunt/Uncle | Aunt|Uncle Nephew|Niece examples |
| 1.0 | 3.0 | 0.0 | GrandAunt/Uncle |  |
| 1.0 | 3.0 | 1.0 | Half GrandAunt/Uncle |  |
| 1.0 | 4.0 | 0.0 | Great-GrandAunt/Uncle |  |
| 1.0 | 4.0 | 2.0 | Spouse of Great-GrandUncle |  |
| 1.0 | 4.0 | 6.0 | Spouse of Great-GrandAunt |  |
| 1.0 | 5.0 | 7.0 | Spouse of half 2nd Great-GrandAunt |  |
| 1.0 | 5.0 | 10.0 | Spouse of half 2nd Great-GrandAunt/Uncle |  |
| 2.0 | 1.0 | 0.0 | Nephew/Niece |  |
| 3.0 | 1.0 | 0.0 | GrandNephew/Niece |  |
| 2.0 | 2.0 | 0.0 | First cousin | Cousin examples |
| 2.0 | 3.0 | 0.0 | First cousin, once removed |  |
| 2.0 | 4.0 | 0.0 | First cousin, twice removed |  |
| 3.0 | 2.0 | 0.0 | First cousin, once removed |  |
| 3.0 | 3.0 | 0.0 | Second cousin |  |
| 3.0 | 4.0 | 0.0 | Second cousin, once removed |  |
| 4.0 | 4.0 | 0.0 | Third cousin |  |
| 999.0 | 1.0 | 0.0 | Self | Special relationships |
| 999.0 | 2.0 | 0.0 | Spouse |  |
| 999.0 | 3.0 | 0.0 | Mother In Law/Father In Law |  |
| 999.0 | 4.0 | 0.0 | Brother In Law/Sister In Law |  |
| 999.0 | 5.0 | 0.0 | Daughter In Law/Son In Law |  |
| PersonTable.Flags |  |  |  |  |
| Prefix description added to Set Relationship display as defined by Relate1/Relate2 calculation: |  |  |  |  |
| 0 = No prefix descriptor |  |  |  |  |
| 1 = "Half" |  |  |  |  |
| 2 = "Spouse of" male blood relation (ie display uses "Father, Uncle, Cousin") |  |  |  |  |
| 3 = "Spouse of half" male blood relation (ie display uses "Father, Uncle, Cousin") |  |  |  |  |
| 6 = "Spouse of" female blood relation (ie display uses "Mother, Aunt, Cousin") |  |  |  |  |
| 7 = "Spouse of half" female blood relation (ie display uses "Mother, Aunt, Cousin") |  |  |  |  |
| 10 = "Spouse of" blood relation where sex is unknown (ie display uses "Mother/Father, Aunt/Uncle, Cousin") |  |  |  |  |
| The Relationshp value can be calculated as follows using the Wikipedia Table of Consanguinity. |  |  |  |  |
| 1. View the Wikipedia Table of Consanguinity. |  |  |  |  |
| 2. Starting from the "Person" box, move the number of columns to the right = to the value of Relate2. |  |  |  |  |
|       This is the # of generations from the person defined in Tools>Set Relationships (or from DNATable.ID2 in the case of DNA Relationships), to the most Recent Common Ancestor (MRCA). |  |  |  |  |
| 3. Move the number of rows down = to the value of Relate1.  |  |  |  |  |
|      This is the # generations from the selected person to the MRCA for Set Relationships (or to DNATable.ID1 in the case of DNA Relationships). |  |  |  |  |
| 4. Add Person.Flags label prefix as appropriate. |  |  |  |  |

## Understanding the System

### Example 1: Aunt Relationship
- **Relate1 = 1**: Person A is 1 generation from MRCA (the common grandparent)
- **Relate2 = 2**: Person B is 2 generations from MRCA (parent of Person A's parent)
- **Flags = 0**: Blood relationship
- **Result**: Person B is Person A's Aunt/Uncle

### Example 2: First Cousin
- **Relate1 = 2**: Person A is 2 generations from MRCA (grandchild of common grandparent)
- **Relate2 = 2**: Person B is 2 generations from MRCA (grandchild of common grandparent)
- **Flags = 0**: Blood relationship
- **Result**: Person B is Person A's First Cousin

### Example 3: First Cousin Once Removed
- **Relate1 = 2**: Person A is 2 generations from MRCA
- **Relate2 = 3**: Person B is 3 generations from MRCA
- **Flags = 0**: Blood relationship
- **Result**: Person B is Person A's First Cousin, Once Removed

### Example 4: Half Sibling
- **Relate1 = 1**: Person A is 1 generation from MRCA (child of common parent)
- **Relate2 = 1**: Person B is 1 generation from MRCA (child of common parent)
- **Flags = 1**: Half relationship (only one common parent)
- **Result**: Person B is Person A's Half Brother/Sister

### Example 5: Spouse of Uncle
- **Relate1 = 1**: Person A is 1 generation from MRCA
- **Relate2 = 4**: Person B's spouse is 4 generations from MRCA
- **Flags = 2**: Spouse of male blood relation
- **Result**: Person B is the Spouse of Person A's Great-Grand Uncle

## Special Cases

### No Blood Relation (Relate1 = 0, Relate2 = 0)
When both values are 0, there is no calculable blood relationship. This might indicate:
- Unrelated individuals
- Relationship not yet established in the database
- Spouse-only relationship without common ancestors

### Complex Relationships
RootsMagic can encode complex scenarios:
- **Half relationships** (Flags = 1)
- **Step relationships** (through marriage, various Flag values)
- **Multiple relationship paths** (may require multiple entries)

## Usage in Database

### PersonTable Fields

The `PersonTable` contains these relationship fields:

- **PersonTable.Relate1**: Stored as INTEGER (0-999)
- **PersonTable.Relate2**: Stored as INTEGER (0-999)
- **PersonTable.Flags**: Stored as INTEGER (0-10)

These fields work in combination with:
- **PersonTable.ParentID**: Links to FamilyTable.FamilyID for parent family
- **PersonTable.SpouseID**: Links to FamilyTable.FamilyID for spouse family

### Calculating Relationships

To display the relationship between two people:

1. Look up both individuals' Relate1, Relate2, and Flags values
2. Determine if direct line (one Relate value is 0) or collateral (both > 0)
3. Apply the appropriate formula:
   - Direct: Use the non-zero value to count generations
   - Collateral siblings: Check if Relate1 = Relate2 = 1
   - Collateral aunt/uncle: One value is 1, the other is ≥ 2
   - Collateral cousins: Both values ≥ 2, calculate degree and removal
4. Apply Flag modifiers for half-relationships or in-law relationships
5. Format the relationship string with appropriate terminology

## Reference

### Common Relationship Patterns

| Pattern | Relationship Type |
|---------|-------------------|
| (0, N, 0) | Ancestor (N generations up) |
| (N, 0, 0) | Descendant (N generations down) |
| (1, 1, 0) | Sibling |
| (1, 1, 1) | Half-sibling |
| (1, 2+, 0) | Aunt/Uncle |
| (2+, 1, 0) | Nephew/Niece |
| (2+, 2+, 0) | Cousin (calculate degree and removal) |
| (N, M, 2) | Spouse of male blood relation |
| (N, M, 6) | Spouse of female blood relation |

## Metadata

- **Source**: RootsMagic 11 Data Definition
- **Source File**: RM11DataDef-V11_0_0-20250914.xlsx
- **Worksheet**: Relationship
- **Version**: 11.0.0
- **Date**: 2025-09-14
