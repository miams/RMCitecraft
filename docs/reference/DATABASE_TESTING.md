# Database Integrity Testing Guide

## Why Comparison-Based Testing is Essential

When inserting new records into the RootsMagic database, schema validation alone is insufficient. RootsMagic has subtle conventions, undocumented fields, and implicit requirements that can only be discovered by comparing created records with existing records.

## Critical Bugs Caught by Comparison Testing

1. **Reverse Field** (99.9% populated, not documented): Tests discovered locations require a reversed hierarchy field ("Country, State, County, City"). Missing this field corrupts the database.

2. **NULL vs 0 for Integer Columns**: RootsMagic requires 0, not NULL, for integer columns (Latitude, Longitude, MasterID, fsID, anID). Schema tests wouldn't catch this.

3. **SortDate is BIGINT**: Field is BIGINT, not INTEGER, despite other ID fields being INTEGER.

4. **Empty Citation Fields for Free-Form Sources**: For TemplateID=0, Footnote/ShortFootnote/Bibliography must be empty in CitationTable (stored in SourceTable.Fields XML instead).

## Methodology: Field-by-Field Comparison

When implementing database operations for a new record type:

### 1. Find Similar Existing Records

```python
# Get an existing record of the same type
cursor.execute("SELECT * FROM PlaceTable WHERE PlaceType = 0 LIMIT 1")
existing = cursor.fetchone()
```

### 2. Create Test Record

```python
# Use your new function to create a record
new_place_id = create_location(...)
cursor.execute("SELECT * FROM PlaceTable WHERE PlaceID = ?", (new_place_id,))
created = cursor.fetchone()
```

### 3. Compare Field-by-Field

```python
# Compare data types
assert type(created[0]) == type(existing[0]), "PlaceID types don't match"

# Compare NULL vs 0 for integers
assert created[4] is not None, "Latitude should not be NULL"
assert created[5] is not None, "Longitude should not be NULL"

# Compare patterns (e.g., Reverse field)
name = created[10]
reverse = created[7]
expected_reverse = ', '.join(reversed([p.strip() for p in name.split(',')]))
assert reverse == expected_reverse, f"Reverse field pattern incorrect"
```

### 4. Validate Foreign Keys

```python
# Cemetery should reference location
cursor.execute("SELECT MasterID FROM PlaceTable WHERE PlaceID = ?", (cemetery_id,))
master_id = cursor.fetchone()[0]
assert master_id == location_id, "Cemetery MasterID should reference location"
```

### 5. Test Full Workflow

```python
# Create source → citation → event → places → links
# Verify all relationships are correct
# Ensure no orphaned records
```

## Required Tests for Each New Record Type

1. **Schema Tests**: Verify all columns exist with correct types
2. **NULL Tests**: Verify no NULL values in integer columns (use 0 instead)
3. **Pattern Tests**: Compare field patterns with existing records
4. **Foreign Key Tests**: Verify all relationships are valid
5. **Workflow Tests**: Test complete end-to-end creation with all dependencies

## Test Organization Pattern

```python
class TestNewRecordTypeIntegrity:
    """Test that new records match existing RootsMagic patterns."""

    def test_schema_columns(self, db_connection):
        """Verify table has expected columns with correct types."""
        # PRAGMA table_info checks

    def test_no_null_integer_columns(self, db_connection):
        """Verify integer columns use 0, not NULL."""
        # Check existing and created records

    def test_record_matches_existing(self, db_connection):
        """Compare created record field-by-field with existing record."""
        # Field-by-field comparison

    def test_full_workflow(self, db_connection, tmp_path):
        """Test complete creation with all dependencies and links."""
        # End-to-end integration test
```

## When to Run These Tests

- **Before every commit** that touches database operations
- **After discovering a new field requirement** (add test to prevent regression)
- **When adding new record types** (sources, citations, events, media, etc.)
- **Before deploying to production** (prevent database corruption)

## Reference Implementation

See `tests/unit/test_database_integrity.py` for comprehensive examples:
- 19 tests covering PlaceTable, SourceTable, CitationTable, EventTable
- Tests caught critical bugs before production deployment

## Testing Philosophy

> "Comparison-based testing reveals what documentation cannot. RootsMagic's database has evolved over 20+ years with subtle conventions that only emerge by studying existing data patterns. A test that compares your created record with an existing record will catch bugs that schema validation alone would miss—potentially months before corruption becomes apparent."

---

**Related Documentation:**
- [Schema Reference](./schema-reference.md) - Complete RootsMagic database schema
- [Database Patterns](./DATABASE_PATTERNS.md) - Common SQL patterns and examples
