---
priority: reference
topics: [database, census, citation, batch, testing]
---

# Database Connection Property Fix

**Date**: 2025-10-25
**Issue**: Census image viewer showing "No census image available"
**Root Cause**: DatabaseConnection class missing `.connection` property

---

## Problem

When the citation processing dialog tried to find census images:

```python
# In citation_manager.py line 1503:
cursor = self.db.connection.cursor()
```

**Error**: `AttributeError: 'DatabaseConnection' object has no attribute 'connection'`

The `DatabaseConnection` class only provided context managers (`get_connection()`, `transaction()`), not a direct `.connection` property.

---

## Solution

Added `connection` property to `DatabaseConnection` class:

**File**: `src/rmcitecraft/repositories/database.py` (lines 94-103)

```python
@property
def connection(self) -> sqlite3.Connection:
    """Get or create database connection.

    Returns:
        Active SQLite connection with RMNOCASE collation loaded.
    """
    if self._connection is None:
        self.connect(read_only=True)
    return self._connection
```

---

## Behavior

**Lazy Connection Initialization:**
- First access to `.connection` automatically calls `connect(read_only=True)`
- ICU extension loaded automatically
- RMNOCASE collation registered
- Subsequent accesses reuse existing connection

**Example Usage:**

```python
# Old way (context manager):
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM PersonTable")

# New way (property - auto-connects):
cursor = db.connection.cursor()
cursor.execute("SELECT * FROM PersonTable")
```

---

## Impact

**Fixed:**
- ✅ Census image viewer now finds persons in database
- ✅ Image lookup works: "Upton Imes (1930)" → PersonID 5624 → 1930 census image
- ✅ RMNOCASE collation works correctly (case-insensitive name matching)

**Unchanged:**
- Context managers (`get_connection()`, `transaction()`) still work as before
- Read-only default maintained for safety
- ICU extension loading unchanged

---

## Testing

Verified the fix works:

```bash
# Test person lookup
cursor = db.connection.cursor()
cursor.execute(
    """
    SELECT p.PersonID, n.Surname, n.Given
    FROM PersonTable p
    JOIN NameTable n ON p.PersonID = n.OwnerID
    WHERE n.Surname COLLATE RMNOCASE = 'Imes'
      AND n.Given COLLATE RMNOCASE LIKE 'Upton%'
    """
)
# Result: Found PersonID 5624 (Upton Imes)

# Test census image lookup
images = media_resolver.get_census_images_for_person(cursor, 5624)
# Result: [(1940, Path(...)), (1930, Path(...)), (1900, Path(...))]
```

---

**Status**: ✅ Fixed and Tested
**Files Modified**: `src/rmcitecraft/repositories/database.py`
