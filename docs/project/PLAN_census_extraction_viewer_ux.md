---
priority: reference
topics: [database, census, citation, batch, ui]
---

# Census Extraction Viewer UX Redesign Plan

## Current State Analysis

The current layout has three equal-weight columns:
1. **Extracted Persons** (1/4 width) - Person list with name, age, birthplace, occupation
2. **Person Details** (2/5 width) - Flat list: Person Info → Extended Fields → Census Page Info → RootsMagic Links → Metadata
3. **Quality Assessment** (flex-1) - Quality management UI

### Problems Identified

1. **Information Hierarchy Issues**
   - Census Page Info is buried at the bottom, but it's crucial context (WHERE was this person?)
   - All fields have equal visual weight - hard to scan
   - Metadata (internal IDs) mixed with useful info

2. **Person List Insufficient Context**
   - Doesn't show census year (critical for multi-year databases)
   - No line number (important for verification against original image)
   - No location context (just birthplace, not where they were enumerated)

3. **Extended Fields Organization**
   - Flat list doesn't distinguish sample line fields (cols 21-33) from regular fields
   - No grouping by column ranges as they appear on the actual census form

4. **Missing Features**
   - No link to dynamic census form template
   - No way to quickly compare extracted data against census image

5. **Secondary Features Take Primary Space**
   - Quality Assessment has equal prominence to core data viewing
   - For verification workflow, viewing data is more important than quality tagging

## Proposed Redesign

### Layout: 3-Column with Prioritized Information

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Header: Title + Stats + Search/Filter Controls                          │
├──────────────┬────────────────────────────────────────┬─────────────────┤
│  PERSONS     │           PERSON DETAILS               │  SECONDARY      │
│  (25%)       │              (50%)                     │    (25%)        │
│              │                                        │                 │
│ ┌──────────┐ │ ┌────────────────────────────────────┐ │ ┌─────────────┐ │
│ │Line Name │ │ │ 📍 CENSUS LOCATION & SOURCE        │ │ │ [Quality]   │ │
│ │Year Loc  │ │ │    (Context Card - Always Visible)  │ │ │ [Metadata]  │ │
│ └──────────┘ │ │    State, County, ED, Sheet/Page    │ │ │             │ │
│ ┌──────────┐ │ │    [View FamilySearch] [View Form]  │ │ │ Tabs or     │ │
│ │...       │ │ └────────────────────────────────────┘ │ │ Expandable  │ │
│ └──────────┘ │ ┌────────────────────────────────────┐ │ │             │ │
│              │ │ 👤 PERSON IDENTITY                  │ │ │             │ │
│ Grouped by   │ │    Name, Relationship, Demographics │ │ │             │ │
│ Page/        │ └────────────────────────────────────┘ │ │             │ │
│ Household    │ ┌────────────────────────────────────┐ │ │             │ │
│              │ │ 💼 EMPLOYMENT (Cols 15-20)         │ │ │             │ │
│              │ │    (If applicable)                  │ │ │             │ │
│              │ └────────────────────────────────────┘ │ │             │ │
│              │ ┌────────────────────────────────────┐ │ │             │ │
│              │ │ 📊 SAMPLE LINE DATA (Cols 21-33)   │ │ │             │ │
│              │ │    (Expandable - only for samples)  │ │ │             │ │
│              │ └────────────────────────────────────┘ │ │             │ │
│              │ ┌────────────────────────────────────┐ │ │             │ │
│              │ │ 🔗 RMTREE LINKS                    │ │ │             │ │
│              │ │    (Expandable)                     │ │ │             │ │
│              │ └────────────────────────────────────┘ │ │             │ │
└──────────────┴────────────────────────────────────────┴─────────────────┘
```

### Detailed Changes

#### 1. Person List (Left Column) - Enhanced

**Current**: Name, Age, Birthplace, Occupation
**Proposed**:
```
┌─────────────────────────────┐
│ ⭐ Line 6 │ 1950 Census      │
│ Iams, Ross L                │
│ San Diego Co., CA • Age 68  │
│ ED 72-91, Sheet 10          │
└─────────────────────────────┘
```

Show:
- Line number (critical for verification)
- Census year badge
- Full name
- Location (County, State abbreviation)
- Age
- ED and Sheet/Page (helps locate on image)
- Target person indicator (star)

#### 2. Person Details (Center Column) - Reorganized Cards

**Card A: Census Location & Source** (ALWAYS FIRST - provides context)
```
┌────────────────────────────────────────────┐
│ 📍 1950 Census - San Diego County, CA      │
├────────────────────────────────────────────┤
│ Township/City: San Diego                   │
│ E.D.: 72-91    Sheet: 10                   │
│ Date: April 4, 1950   Enum: Bertha Harris  │
│                                            │
│ [View on FamilySearch] [View Census Form]  │
│         [Edit] [Save] [Cancel]             │
└────────────────────────────────────────────┘
```

**Card B: Person Identity** (Core demographics)
```
┌────────────────────────────────────────────┐
│ 👤 Person Identity                         │
├─────────────────────┬──────────────────────┤
│ Name: Iams, Ross L  │ Line: 6              │
│ Rel: Head           │ HH/Dwell: 111/111    │
├─────────────────────┼──────────────────────┤
│ Sex: M   Race: W    │ Age: 68              │
│ Marital: Married    │ Birth: Pennsylvania  │
└─────────────────────┴──────────────────────┘
```

**Card C: Employment** (Cols 15-20 - show if has data)
```
┌────────────────────────────────────────────┐
│ 💼 Employment (Cols 15-20)                 │
├────────────────────────────────────────────┤
│ Status: Other (Ot)   Work Last Week: No    │
│ Looking: No          Hours: -              │
│ Occupation: -        Industry: -           │
│ Class: -                                   │
└────────────────────────────────────────────┘
```

**Card D: Sample Line Data** (Cols 21-33 - ONLY for sample persons, expandable)
```
┌────────────────────────────────────────────┐
│ 📊 Sample Line Data (Lines 1,6,11,16,21,26)│ ▼
├────────────────────────────────────────────┤
│ Residence April 1949:                      │
│   Same House: -  On Farm: No  Same County: Yes │
│ Education:                                 │
│   Highest Grade: C1  Completed: Yes        │
│ Income 1949:                               │
│   Wages: $3,800  Self-Emp: -  Other: None  │
│ Veteran: No  WW1: No  WW2: Yes             │
└────────────────────────────────────────────┘
```

**Card E: Relationships & Links** (Expandable)
- Parents' birthplaces
- RootsMagic links (Citation ID, Person ID, confidence)

#### 3. Secondary Panel (Right Column) - Tabbed

**Tab 1: Quality Assessment**
- Current quality UI, slightly condensed
- Quick quality indicators per field

**Tab 2: Debug / Metadata**
- Person ID, Page ID
- FamilySearch ARK
- Extraction timestamp
- Batch info

### Implementation Steps

1. Update person list item rendering
2. Reorganize detail view into cards with clear hierarchy
3. Add "View Census Form" button that calls the new renderer
4. Move metadata to secondary tab
5. Make Sample Line section expandable/collapsible
6. Add census year and location to person list items
7. Group extended fields by census form column ranges

### Key UX Principles Applied

1. **Progressive Disclosure**: Most important info first, details expandable
2. **Context Before Details**: Location/source establishes WHERE before WHO
3. **Scannable**: Each card has a clear purpose and icon
4. **Verification Workflow**: Easy to compare with original image
5. **Secondary Functions Secondary**: Quality/metadata don't compete with viewing
