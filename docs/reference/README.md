# RootsMagic Database Reference Documentation

**Comprehensive reference materials for working with RootsMagic databases**

This directory contains detailed documentation for understanding and working with RootsMagic database structure, conventions, and best practices.

---

## Quick Navigation

### 📊 Database Schema
- **[schema-reference.md](schema-reference.md)** - Complete table schemas with field definitions
- **[schema.json](schema.json)** - Machine-readable schema definition

### 🔗 Relationships & Linking
- **[relationships.md](relationships.md)** - How tables relate to each other
- **[citation-link-best-practices.md](citation-link-best-practices.md)** - **NEW** Empirical guide for CitationLinkTable (99.8% field population rates)

### 📋 Data Formats
- **[data-formats/](data-formats/)** - BLOB formats, dates, places, templates
  - `blob-source-fields.md` - SourceTable.Fields XML structure
  - `blob-citation-fields.md` - CitationTable.Fields XML structure
  - `blob-template-field-defs.md` - Template field definitions
  - `date-format.md` - Date encoding and SortDate
  - `place-format.md` - Hierarchical place names
  - `fact-types.md` - Event/Fact type codes
  - `sentence-templates.md` - Sentence template structure

### 🔍 Query Patterns
- **[query-patterns/](query-patterns/)** - Common queries and validation
  - `query-patterns.md` - Standard query patterns for common operations
  - `data-quality-rules.md` - Validation rules for data integrity

### 📝 Specialized Topics
- **[event-table-details.md](event-table-details.md)** - Event/Fact handling details
- **[name-display-logic.md](name-display-logic.md)** - Name formatting and display rules

### 🗄️ RMCitecraft State Databases
- **[BATCH_STATE_DATABASE_SCHEMA.md](BATCH_STATE_DATABASE_SCHEMA.md)** - Batch processing state (`~/.rmcitecraft/batch_state.db`)
- **[CENSUS_EXTRACTION_DATABASE_SCHEMA.md](CENSUS_EXTRACTION_DATABASE_SCHEMA.md)** - **NEW** Census extraction storage (`~/.rmcitecraft/census.db`)
- **[DATABASE_PATTERNS.md](DATABASE_PATTERNS.md)** - SQL patterns and database connection examples
- **[DATABASE_TESTING.md](DATABASE_TESTING.md)** - Comparison-based testing methodology

---

## Documentation Purpose

### For Developers
- **Schema understanding**: Table structures, field types, constraints
- **Best practices**: Field population patterns from production databases
- **Query examples**: Tested SQL patterns for common operations
- **Data validation**: Rules for ensuring database integrity

### For AI Agents
- **Context loading**: Comprehensive reference for code generation
- **Convention learning**: Empirical patterns from real databases
- **Error prevention**: Common mistakes and how to avoid them
- **Testing guidance**: Validation approaches for new code

---

## Critical Learnings from Database Analysis

### Schema Documentation vs Reality

The schema documentation is based on RootsMagic specifications, but **empirical analysis of production databases reveals critical differences**:

#### CitationLinkTable (from citation-link-best-practices.md)
- **Schema says**: "IsPrivate: Not Implemented"
- **Reality**: 99.8% of records have `IsPrivate = 0`
- **Schema says**: "Flags: Not Implemented"
- **Reality**: 99.8% of records have `Flags = 0`
- **Schema says**: "Quality: 3-Character Quality"
- **Reality**: 99.8% populated (not optional as implied)

**Lesson**: Always validate against production databases, not just schema docs.

#### PlaceTable (from database integrity tests)
- **Schema says**: "Reverse: Calculated field"
- **Reality**: 99.9% manually populated with reversed hierarchy
- **Pattern**: "City, County, State, Country" → "Country, State, County, City"
- **Critical**: Missing this field corrupts database

#### Integer Columns (PlaceTable, EventTable)
- **Schema says**: INTEGER type
- **Reality**: RootsMagic requires `0`, not `NULL` for:
  - `Latitude`, `Longitude`, `LatLongExact`
  - `MasterID`, `fsID`, `anID`
- **Impact**: NULL values cause RootsMagic errors

---

## Testing Philosophy

> **"Comparison-based testing reveals what documentation cannot."**

When implementing database operations:

1. **Find existing records** of the same type
2. **Create test record** using your code
3. **Compare field-by-field** (types, values, patterns)
4. **Validate foreign keys** and relationships
5. **Test full workflow** (end-to-end)

See `citation-link-best-practices.md` for detailed testing examples.

---

## Document Organization

```
docs/reference/
├── README.md                              # This file
├── schema-reference.md                    # Complete schema
├── schema.json                            # Machine-readable schema
├── relationships.md                       # Table relationships
├── citation-link-best-practices.md        # CitationLink empirical guide (NEW)
├── event-table-details.md                 # Event/Fact details
├── name-display-logic.md                  # Name formatting
├── data-formats/                          # Data encoding formats
│   ├── blob-source-fields.md
│   ├── blob-citation-fields.md
│   ├── blob-template-field-defs.md
│   ├── date-format.md
│   ├── place-format.md
│   ├── fact-types.md
│   └── sentence-templates.md
└── query-patterns/                        # SQL patterns & validation
    ├── query-patterns.md
    └── data-quality-rules.md
```

---

## How to Use This Documentation

### Starting a New Feature

1. **Read schema-reference.md** for table structure
2. **Check query-patterns/** for similar operations
3. **Review best practices docs** (citation-link-best-practices.md, etc.)
4. **Implement with tests** (comparison-based testing)
5. **Validate** against data-quality-rules.md

### Debugging Database Issues

1. **Check relationships.md** for FK relationships
2. **Review schema-reference.md** for field constraints
3. **Compare with data-quality-rules.md** validation queries
4. **Check best practices docs** for field population patterns

### Understanding BLOB Fields

1. **Start with data-formats/** directory
2. **Review blob-source-fields.md** or blob-citation-fields.md
3. **Check blob-template-field-defs.md** for template fields
4. **Test with working database** for validation

---

## Key Reference Patterns

### OwnerType Values (Common in Link Tables)

```
0  = Person (PersonTable)
1  = Family (FamilyTable)
2  = Event (EventTable)
3  = Source (SourceTable)
4  = Citation (CitationTable)
5  = Place (PlaceTable)
6  = Task (TaskTable)
7  = Name (NameTable)
19 = Association
```

### EventType (FactTypeID) Common Values

```
1  = Birth
2  = Death
3  = Burial
4  = Also use 4 for Burial (alternate)
18 = Census
```

See `data-formats/fact-types.md` for complete list.

### Date Format (SortDate)

- **Type**: BIGINT
- **Format**: Encoded date for chronological sorting
- **NULL**: Acceptable for unknown dates
- **Reference**: `data-formats/date-format.md`

### Place Hierarchy

- **Format**: Comma-delimited (City, County, State, Country)
- **Reverse**: Required field with reversed order
- **Type**: 0=Place, 2=Place Detail (cemetery)
- **Reference**: `data-formats/place-format.md`

---

## Contribution Guidelines

When adding new documentation:

1. **Base on empirical analysis** of production databases
2. **Include SQL queries** demonstrating patterns
3. **Show field population rates** (X% of records have Y)
4. **Provide testing examples** (comparison-based tests)
5. **Document deviation from schema** when found
6. **Cross-reference** related documents
7. **Update this README** with new document links

---

## Related Documentation

- **[CLAUDE.md](/CLAUDE.md)** - Development guidance and workflow
- **[AGENTS.md](/AGENTS.md)** - Machine-readable instructions for AI agents
- **[tests/unit/test_database_integrity.py](/tests/unit/test_database_integrity.py)** - Reference implementation of comparison-based tests

---

**Last Updated**: 2025-11-17
**Maintained By**: RMCitecraft project
**Purpose**: Ensure database integrity through empirical understanding of RootsMagic conventions
