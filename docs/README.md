---
priority: essential
topics: [database, census, citation, batch, findagrave]
---

# RMCitecraft Documentation

**Comprehensive documentation for RMCitecraft development and RootsMagic database operations**

This directory contains implementation guides, database reference materials, and testing documentation.

---

## 📚 Documentation Categories

### 🔧 Database Reference (Start Here)
**[reference/](reference/)** - RootsMagic database schema, patterns, and best practices

Essential reading for database operations:
- **[reference/README.md](reference/README.md)** - Navigation guide for reference docs
- **[reference/citation-link-best-practices.md](reference/citation-link-best-practices.md)** - Critical: 99.8% field population requirements
- **[reference/schema-reference.md](reference/schema-reference.md)** - Complete table schemas
- **[reference/query-patterns/](reference/query-patterns/)** - SQL patterns and validation rules

### 🧪 Testing & Validation
- **[E2E-TESTING-QUICKSTART.md](E2E-TESTING-QUICKSTART.md)** - End-to-end testing guide
- **[TEST-IMAGE-DOWNLOAD.md](TEST-IMAGE-DOWNLOAD.md)** - Image download testing
- **[../tests/unit/test_database_integrity.py](../tests/unit/test_database_integrity.py)** - Database integrity test suite (23 tests)

### 📋 Implementation Guides

#### Find a Grave Batch Processing
- **[FINDAGRAVE-IMPLEMENTATION.md](FINDAGRAVE-IMPLEMENTATION.md)** - Find a Grave automation overview
- **[BATCH_PROCESSING_UI_DESIGN.md](BATCH_PROCESSING_UI_DESIGN.md)** - Batch UI design and workflow
- **[BATCH_PROCESSING_PHASE1_IMPLEMENTATION.md](BATCH_PROCESSING_PHASE1_IMPLEMENTATION.md)** - Phase 1 implementation
- **[BATCH_PROCESSING_BUGFIXES.md](BATCH_PROCESSING_BUGFIXES.md)** - Bug fixes and improvements
- **[BATCH_PROCESSING_ASYNC_FIX.md](BATCH_PROCESSING_ASYNC_FIX.md)** - Async processing fixes
- **[BATCH_PROCESSING_FINAL_FIXES.md](BATCH_PROCESSING_FINAL_FIXES.md)** - Final improvements

#### Census Data Processing
- **[1930_CENSUS_QUICK_SUMMARY.md](1930_CENSUS_QUICK_SUMMARY.md)** - Quick reference
- **[1930_CENSUS_ED_EXTRACTION_ISSUE.md](1930_CENSUS_ED_EXTRACTION_ISSUE.md)** - ED extraction issue
- **[1930_CENSUS_INVESTIGATION_SUMMARY.md](1930_CENSUS_INVESTIGATION_SUMMARY.md)** - Investigation summary

#### Place & Gazetteer
- **[PLACEDB-FORMAT-ANALYSIS.md](PLACEDB-FORMAT-ANALYSIS.md)** - PlaceDB.dat format analysis
- **[GAZETTEER.md](GAZETTEER.md)** - Gazetteer validation system
- **[COUNTYCHECKDB.md](COUNTYCHECKDB.md)** - County validation database

#### UI & Logging
- **[ERROR-HANDLING-UI.md](ERROR-HANDLING-UI.md)** - Error handling UI design
- **[MESSAGE_LOG_IMPLEMENTATION.md](MESSAGE_LOG_IMPLEMENTATION.md)** - Message log system
- **[UI-LOGGING.md](UI-LOGGING.md)** - UI logging patterns

#### Image Processing
- **[IMAGE-DOWNLOAD-WORKFLOW.md](IMAGE-DOWNLOAD-WORKFLOW.md)** - Image download workflow

#### Testing Infrastructure
- **[PLAYWRIGHT-MIGRATION.md](PLAYWRIGHT-MIGRATION.md)** - Playwright migration guide

---

## 🚀 Quick Start Guides

### For New Developers

1. **Understand the database**: Read [reference/README.md](reference/README.md)
2. **Learn critical patterns**: Review [reference/citation-link-best-practices.md](reference/citation-link-best-practices.md)
3. **Study the schema**: [reference/schema-reference.md](reference/schema-reference.md)
4. **Review test suite**: [../tests/unit/test_database_integrity.py](../tests/unit/test_database_integrity.py)

### For AI Agents

Load these documents for database operations:
```
1. /docs/reference/README.md
2. /docs/reference/citation-link-best-practices.md
3. /docs/reference/schema-reference.md
4. /docs/reference/query-patterns/data-quality-rules.md
5. /CLAUDE.md (section: Database Integrity Testing)
6. /AGENTS.md (section: Database Integrity Tests)
```

### Implementing Database Operations

**Critical Reading Order:**
1. **[reference/citation-link-best-practices.md](reference/citation-link-best-practices.md)** - Field population patterns
2. **[reference/query-patterns/query-patterns.md](reference/query-patterns/query-patterns.md)** - SQL patterns
3. **[reference/query-patterns/data-quality-rules.md](reference/query-patterns/data-quality-rules.md)** - Validation rules
4. **[../CLAUDE.md](../CLAUDE.md)** - Testing philosophy (comparison-based testing)

**Testing Pattern:**
```python
# 1. Read existing records
# 2. Create test record
# 3. Compare field-by-field
# 4. Validate relationships
# 5. Test full workflow
```

See [reference/citation-link-best-practices.md](reference/citation-link-best-practices.md) for complete examples.

---

## 🎯 Key Learnings from Database Analysis

### Critical Bugs Caught by Comparison Testing

#### 1. Missing Citation Link Fields (99.8% population rate)
**Impact**: All citation links were missing `Quality`, `IsPrivate`, `Flags` fields
**Discovery**: Comparison-based tests revealed 99.8% of existing records have these fields
**Schema docs said**: "Not Implemented"
**Reality**: Critical for database integrity
**Reference**: [reference/citation-link-best-practices.md](reference/citation-link-best-practices.md)

#### 2. Missing Reverse Field (99.9% population rate)
**Impact**: Locations missing reversed hierarchy field
**Discovery**: Tests showed 99.9% of locations have `Reverse` field populated
**Pattern**: "City, County, State, Country" → "Country, State, County, City"
**Fix**: Added Reverse field generation to all place creation code

#### 3. NULL vs 0 for Integer Columns
**Impact**: 464 places had NULL values instead of 0 for Latitude, Longitude, MasterID, etc.
**Discovery**: RootsMagic error: `" is not a valid integer value`
**Fix**: Updated all INSERT statements to use 0, not NULL

#### 4. SortDate Data Type
**Impact**: Test failed - expected INTEGER, database has BIGINT
**Discovery**: Schema mismatch for EventTable.SortDate
**Fix**: Updated test to check for BIGINT

### Testing Philosophy

> **"Schema validation alone is insufficient. RootsMagic has subtle conventions that only emerge from comparing with existing data patterns."**

**Comparison-Based Testing**:
1. Find existing records of the same type
2. Create test record using your code
3. Compare field-by-field (types, values, patterns)
4. Validate foreign keys and relationships
5. Test complete workflow end-to-end

**Reference Implementation**:
- [../tests/unit/test_database_integrity.py](../tests/unit/test_database_integrity.py) - 23 comprehensive tests
- [reference/citation-link-best-practices.md](reference/citation-link-best-practices.md) - Testing examples

---

## 📊 Documentation Map by Feature

### Find a Grave Automation
```
Implementation: FINDAGRAVE-IMPLEMENTATION.md
Batch UI:       BATCH_PROCESSING_UI_DESIGN.md
Database:       reference/citation-link-best-practices.md
Testing:        ../tests/unit/test_database_integrity.py
Validation:     reference/query-patterns/data-quality-rules.md
```

### Census Processing
```
1930 Census:    1930_CENSUS_QUICK_SUMMARY.md
Implementation: (future) PRD.md Section 7
Database:       reference/schema-reference.md
Data formats:   reference/data-formats/
```

### Place Management
```
Format:         PLACEDB-FORMAT-ANALYSIS.md
Validation:     GAZETTEER.md, COUNTYCHECKDB.md
Database:       reference/schema-reference.md (PlaceTable)
Query patterns: reference/query-patterns/query-patterns.md
```

### Image Processing
```
Workflow:       IMAGE-DOWNLOAD-WORKFLOW.md
Testing:        TEST-IMAGE-DOWNLOAD.md
Implementation: (in progress)
```

---

## 🔍 Finding Documentation

### By Topic

| Topic | Primary Document | Supporting Docs |
|-------|-----------------|-----------------|
| Database schema | reference/schema-reference.md | reference/README.md |
| Citation linking | reference/citation-link-best-practices.md | reference/relationships.md |
| Data quality | reference/query-patterns/data-quality-rules.md | test_database_integrity.py |
| SQL patterns | reference/query-patterns/query-patterns.md | schema-reference.md |
| Find a Grave | FINDAGRAVE-IMPLEMENTATION.md | BATCH_PROCESSING_*.md |
| Testing | E2E-TESTING-QUICKSTART.md | TEST-*.md |
| Places | PLACEDB-FORMAT-ANALYSIS.md | GAZETTEER.md |

### By Development Phase

| Phase | Documents |
|-------|-----------|
| Planning | PRD.md, *-DESIGN.md |
| Implementation | FINDAGRAVE-IMPLEMENTATION.md, BATCH_PROCESSING_PHASE*.md |
| Testing | E2E-TESTING-QUICKSTART.md, test_database_integrity.py |
| Debugging | ERROR-HANDLING-UI.md, MESSAGE_LOG_IMPLEMENTATION.md |
| Validation | reference/query-patterns/data-quality-rules.md |

---

## 📝 Documentation Standards

### Creating New Documentation

When adding new documentation:

1. **Name convention**: `FEATURE-TOPIC.md` (uppercase)
2. **Update this README**: Add to relevant section
3. **Cross-reference**: Link to related docs
4. **Include examples**: SQL queries, code snippets, test patterns
5. **Document findings**: Empirical analysis, not just theory

### Database Documentation

For database-related docs:

1. **Empirical analysis first**: Query production database for patterns
2. **Field population rates**: Document X% of records have Y
3. **Comparison testing**: Show how to verify against existing records
4. **Schema deviations**: Document when reality differs from schema docs
5. **Add to reference/**: Place in `docs/reference/` directory

### Implementation Documentation

For feature implementations:

1. **Context**: Why this feature exists
2. **Design**: Architecture and approach
3. **Implementation**: Code structure and key files
4. **Testing**: How to test the feature
5. **Known issues**: Bugs, limitations, future work

---

## 🔗 Related Documentation

### Root Level Docs
- **[../README.md](../README.md)** - Project overview
- **[../CLAUDE.md](../CLAUDE.md)** - Development guidance (comprehensive)
- **[../AGENTS.md](../AGENTS.md)** - Machine-readable instructions for AI agents
- **[../PRD.md](../PRD.md)** - Product requirements document

### Test Suite
- **[../tests/unit/test_database_integrity.py](../tests/unit/test_database_integrity.py)** - 23 database integrity tests
- **[../tests/e2e/](../tests/e2e/)** - End-to-end tests
- **[../tests/unit/](../tests/unit/)** - Unit tests

### Configuration
- **[../config/.env.example](../config/.env.example)** - Configuration template
- **[../pyproject.toml](../pyproject.toml)** - Project configuration

---

## 📞 Getting Help

1. **Database questions**: Start with [reference/README.md](reference/README.md)
2. **Feature implementation**: Check relevant IMPLEMENTATION.md doc
3. **Testing**: See E2E-TESTING-QUICKSTART.md or test_database_integrity.py
4. **Development workflow**: Read [../CLAUDE.md](../CLAUDE.md)

---

**Last Updated**: 2025-11-17
**Total Documents**: 30+ (19 implementation, 12+ reference)
**Test Coverage**: 23 database integrity tests, end-to-end test suite
**Purpose**: Ensure database integrity through empirical understanding and comprehensive testing
