---
priority: reference
topics: [database, citation, batch, findagrave, testing]
---

# Code Maintainability Assessment

**Assessment Date**: 2025-11-17
**Scope**: Find a Grave Batch Processing Feature
**Overall Status**: ⚠️ **NEEDS REFACTORING**

---

## Executive Summary

The Find a Grave batch processing feature is **functional but not maintainable**. While the code works and has good test coverage for database integrity, it violates several software engineering principles that will make future maintenance difficult and error-prone.

**Key Issues:**
- Massive functions (up to 406 lines)
- Excessive nesting (up to 11 levels deep)
- Very high cyclomatic complexity (~200 per file)
- Poor separation of concerns
- Difficult to test individual components

**Recommendation**: **Refactor before adding new features**

---

## Detailed Analysis

### File Size Analysis

| File | Lines | Status |
|------|-------|--------|
| `findagrave_batch.py` | 1,194 | ⚠️ Too large |
| `findagrave_queries.py` | 1,379 | ⚠️ Too large |
| `findagrave_automation.py` | 1,039 | ⚠️ Too large |
| **Total** | **3,612** | |

**Industry Standard**: Files should ideally be under 500 lines.

### Function Size Analysis

#### findagrave_batch.py (UI)

| Function | Lines | Status | Issue |
|----------|-------|--------|-------|
| `_start_batch_processing` | 352 | 🔴 Critical | God method - does everything |
| `toggle_sort` | 91 | 🟡 Warning | Should be extracted |
| `_download_photo` | 82 | 🟡 Warning | Mixed concerns |
| `_load_batch` | 60 | 🟡 Warning | Acceptable |
| `_render_item_details` | 51 | 🟢 OK | Borderline |

**Statistics:**
- Average function size: 38.7 lines
- Large functions (>50 lines): 5 (16.7%)
- Very large (>100 lines): 1 (3.3%)

**Industry Standard**: Functions should be under 50 lines, ideally under 20.

#### findagrave_queries.py (Database)

| Function | Lines | Status | Issue |
|----------|-------|--------|-------|
| `create_burial_event_and_link_citation` | 406 | 🔴 Critical | Massive god function |
| `link_citation_to_families` | 229 | 🔴 Critical | Too complex |
| `validate_place_with_gazetteer` | 125 | 🔴 Critical | Should be split |
| `create_location_and_cemetery` | 119 | 🔴 Critical | Two operations in one |
| `find_findagrave_people` | 118 | 🔴 Critical | Complex query logic |
| `create_findagrave_source_and_citation` | 116 | 🔴 Critical | Two operations in one |

**Statistics:**
- Average function size: 104.5 lines
- Large functions (>50 lines): 8 (61.5%)
- Very large (>100 lines): 6 (46.2%)

**Critical**: Nearly half the functions are over 100 lines!

#### findagrave_automation.py (Scraping)

| Function | Lines | Status | Issue |
|----------|-------|--------|-------|
| `_extract_source_comment` | 300 | 🔴 Critical | Massive parser |
| `extract_memorial_data` | 265 | 🔴 Critical | Should be modular |
| `_extract_photo_metadata` | 162 | 🔴 Critical | Too complex |
| `_extract_captions_from_json` | 98 | 🟡 Warning | Borderline |

**Statistics:**
- Average function size: 89.0 lines
- Large functions (>50 lines): 4 (36.4%)
- Very large (>100 lines): 3 (27.3%)

### Complexity Analysis

| File | Max Nesting | Cyclomatic Complexity | Database Ops | Risk Level |
|------|-------------|----------------------|--------------|------------|
| `findagrave_batch.py` | 9 levels | ~178 | 2 | 🔴 VERY HIGH |
| `findagrave_queries.py` | 8 levels | ~197 | 38 | 🔴 VERY HIGH |
| `findagrave_automation.py` | 11 levels | ~197 | 0 | 🔴 VERY HIGH |

**Industry Standards:**
- Max nesting: 3-4 levels
- Cyclomatic complexity: <10 per function, <50 per file
- Nesting >11 levels: Unmaintainable

---

## Specific Problems

### 1. God Functions

**`create_burial_event_and_link_citation` (406 lines)**

This function does:
1. Checks for existing burial events
2. Normalizes location names
3. Searches for existing places
4. Calculates similarity scores
5. Validates with gazetteer
6. Creates location records
7. Creates cemetery records
8. Calculates burial dates
9. Creates burial events
10. Links citations
11. Logs extensively
12. Handles user approval workflow

**Problem**: Violates Single Responsibility Principle - should be 10+ separate functions.

**Impact**:
- Impossible to test individual steps
- Hard to debug (which of 400 lines failed?)
- Can't reuse logic (e.g., place matching)
- High cognitive load for developers

### 2. Excessive Nesting

**Example from `findagrave_automation.py`:**
```python
if condition1:
    if condition2:
        if condition3:
            if condition4:
                if condition5:
                    if condition6:
                        if condition7:
                            if condition8:
                                if condition9:
                                    if condition10:
                                        if condition11:  # 11 levels deep!
                                            do_something()
```

**Problem**: Human brain can only track 4-7 levels comfortably.

**Impact**:
- Hard to reason about code
- Easy to introduce bugs
- Difficult to modify

### 3. Mixed Concerns

Functions mix:
- Business logic
- Database operations
- UI operations
- Logging
- Error handling

**Example**: `_start_batch_processing` handles UI updates, business logic, and orchestration all in one 352-line function.

### 4. Poor Testability

**Current State:**
- Can only test entire workflows
- Can't unit test individual steps
- Hard to mock dependencies
- Tests become integration tests

**Impact**:
- Slow test execution
- Hard to isolate failures
- Low test coverage for edge cases

### 5. Tight Coupling

**Example**: UI code directly calls database functions:
```python
# In findagrave_batch.py (UI layer)
result = create_burial_event_and_link_citation(...)  # Database layer
```

**Problem**: UI is tightly coupled to database implementation.

**Impact**:
- Can't change database layer without affecting UI
- Can't test UI without real database
- Hard to add caching, retries, etc.

---

## Refactoring Recommendations

### Priority 1: Critical (Do Now)

#### 1.1 Break Up God Functions

**`create_burial_event_and_link_citation` → Multiple Functions:**

```python
# BEFORE: 406 lines
def create_burial_event_and_link_citation(...):
    # 406 lines of everything

# AFTER: Orchestrator + helpers
def create_burial_event_and_link_citation(...):
    """Orchestrate burial event creation (20-30 lines)."""
    existing_event = check_for_existing_burial_event(person_id)
    if existing_event:
        return link_to_existing(citation_id, existing_event)

    location = resolve_burial_location(cemetery_data)
    cemetery = resolve_cemetery(location, cemetery_name)
    burial_date = calculate_burial_date(person_id)
    event_id = create_event_record(person_id, location, cemetery, burial_date)
    link_citation_to_event(citation_id, event_id)
    return {'burial_event_id': event_id, ...}

# Separate concerns into focused functions (30-50 lines each):
def resolve_burial_location(cemetery_data) -> PlaceResolution:
    """Find or create burial location with user approval if needed."""
    ...

def calculate_burial_date(person_id) -> tuple[str, int]:
    """Calculate burial date based on death date."""
    ...

def create_event_record(...) -> int:
    """Insert burial event record into database."""
    ...
```

**Benefits:**
- Each function has one job
- Easy to test individually
- Easy to understand
- Reusable components

#### 1.2 Extract Place Matching Logic

```python
# NEW: src/rmcitecraft/services/place_matcher.py

class PlaceMatcher:
    """Service for matching Find a Grave locations to database places."""

    def __init__(self, db_path: str, gazetteer: Gazetteer):
        self.db_path = db_path
        self.gazetteer = gazetteer

    def find_best_match(self, fg_location: str, candidates: list) -> PlaceMatch:
        """Find best matching place from candidates."""
        ...

    def calculate_similarity(self, location1: str, location2: str) -> float:
        """Calculate similarity between two locations."""
        ...

    def validate_with_gazetteer(self, location: str) -> GazetteerResult:
        """Validate location components against gazetteer."""
        ...
```

**Benefits:**
- Reusable across features
- Testable in isolation
- Clear API

#### 1.3 Create Service Layer

```python
# NEW: src/rmcitecraft/services/burial_event_service.py

class BurialEventService:
    """Business logic for burial events (no database code)."""

    def __init__(self, db_repo: BurialEventRepository, place_matcher: PlaceMatcher):
        self.db = db_repo
        self.place_matcher = place_matcher

    async def create_burial_event(self, person_id: int, citation_id: int,
                                   cemetery_data: dict, approval_callback) -> BurialEvent:
        """Create burial event with user approval workflow."""
        # Business logic only, delegates to repository for DB
        ...
```

**Benefits:**
- Business logic separate from database
- Easy to test with mocks
- Can swap database implementation

### Priority 2: Important (Do Soon)

#### 2.1 Reduce Nesting with Early Returns

```python
# BEFORE (nested):
def process_item(item):
    if item.is_valid():
        if item.has_data():
            if item.can_process():
                result = process(item)
                if result.success:
                    return result
    return None

# AFTER (flat):
def process_item(item):
    if not item.is_valid():
        return None
    if not item.has_data():
        return None
    if not item.can_process():
        return None

    result = process(item)
    if not result.success:
        return None

    return result
```

**Benefits:**
- Easier to read
- Lower cognitive load
- Easier to debug

#### 2.2 Extract Constants and Configuration

```python
# NEW: src/rmcitecraft/config/burial_event_config.py

@dataclass
class BurialEventConfig:
    """Configuration for burial event processing."""
    PLACE_MATCH_THRESHOLD: float = 0.95  # 95% similarity required
    MIN_GAZETTEER_CONFIDENCE: str = 'medium'
    MAX_PLACE_CANDIDATES: int = 10
    DEFAULT_QUALITY: str = '~~~'  # Find a Grave default

config = BurialEventConfig()
```

**Benefits:**
- Easy to find and modify settings
- Type-safe configuration
- Self-documenting

#### 2.3 Add Type Hints Everywhere

```python
# BEFORE:
def create_location(name, cemetery):
    ...

# AFTER:
def create_location(
    location_name: str,
    cemetery_name: str
) -> tuple[int, int]:
    """
    Create location and cemetery records.

    Returns:
        Tuple of (location_id, cemetery_id)
    """
    ...
```

**Benefits:**
- IDE autocomplete
- Catch bugs at development time
- Self-documenting

### Priority 3: Nice to Have (Do Later)

#### 3.1 Add Result Types Instead of Dictionaries

```python
# BEFORE:
return {
    'burial_event_id': 123,
    'place_id': 456,
    'cemetery_id': 789,
    'needs_approval': False,
}

# AFTER:
@dataclass
class BurialEventResult:
    burial_event_id: int
    place_id: int
    cemetery_id: int
    needs_approval: bool

return BurialEventResult(
    burial_event_id=123,
    place_id=456,
    cemetery_id=789,
    needs_approval=False,
)
```

**Benefits:**
- Type-safe returns
- IDE autocomplete
- Catch typos at development time

#### 3.2 Use Domain Models

```python
# NEW: src/rmcitecraft/models/burial_event.py

@dataclass
class CemeteryLocation:
    """Domain model for cemetery location."""
    name: str
    city: str | None
    county: str | None
    state: str | None
    country: str | None

    @property
    def full_name(self) -> str:
        """Get full hierarchical name."""
        parts = [p for p in [self.city, self.county, self.state, self.country] if p]
        return ", ".join(parts)
```

---

## Comparison: Current vs. Proposed Architecture

### Current Architecture (Problematic)

```
┌─────────────────────────────────────┐
│        UI Layer (1,194 lines)       │
│  ┌────────────────────────────────┐ │
│  │ _start_batch_processing (352L) │ │
│  │  - UI updates                  │ │
│  │  - Business logic              │ │
│  │  - Direct DB calls             │ │
│  │  - Error handling              │ │
│  │  - Logging                     │ │
│  └────────────────────────────────┘ │
└─────────────────┬───────────────────┘
                  │ Direct coupling
                  ↓
┌─────────────────────────────────────┐
│    Database Layer (1,379 lines)     │
│  ┌────────────────────────────────┐ │
│  │ create_burial_event... (406L)  │ │
│  │  - DB operations               │ │
│  │  - Business logic              │ │
│  │  - Place matching              │ │
│  │  - Validation                  │ │
│  │  - Logging                     │ │
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘
```

**Problems:**
- UI directly coupled to database
- Business logic scattered
- Can't test in isolation
- Hard to modify

### Proposed Architecture (Clean)

```
┌─────────────────────────────────────┐
│         UI Layer (Thin)             │
│  - Render components                │
│  - Handle user input                │
│  - Delegates to service layer       │
└─────────────────┬───────────────────┘
                  │ Loose coupling via interfaces
                  ↓
┌─────────────────────────────────────┐
│      Service Layer (Business)       │
│  - BurialEventService               │
│  - PlaceMatcher                     │
│  - ValidationService                │
│  - Orchestrates workflow            │
└──────────┬───────────────┬──────────┘
           │               │
           ↓               ↓
┌──────────────┐  ┌────────────────┐
│ Repositories │  │    Models      │
│  - BurialRepo│  │  - BurialEvent │
│  - PlaceRepo │  │  - Cemetery    │
│  - CitationR │  │  - Citation    │
└──────────────┘  └────────────────┘
```

**Benefits:**
- Each layer has clear responsibility
- Easy to test each layer
- Can swap implementations
- Business logic is reusable

---

## Testing Impact

### Current State

```python
# Can only test the entire 406-line monster
def test_create_burial_event_full_workflow():
    """Test requires real database, real data, everything."""
    result = create_burial_event_and_link_citation(...)
    # If this fails, where did it fail? Line 50? 200? 350?
```

### After Refactoring

```python
# Can test each piece independently
def test_place_matcher_finds_exact_match():
    matcher = PlaceMatcher(mock_db, mock_gazetteer)
    match = matcher.find_best_match("Kirtland, Lake, Ohio, USA", candidates)
    assert match.similarity > 0.99

def test_burial_date_calculation_after_death():
    service = BurialEventService(mock_repo, mock_matcher)
    burial_date = service.calculate_burial_date(person_with_death_date)
    assert burial_date.modifier == "after"

def test_event_creation_with_approval():
    service = BurialEventService(mock_repo, mock_matcher)
    event = await service.create_burial_event(..., approval_callback=mock_callback)
    assert mock_callback.called_once()
```

---

## Migration Strategy

### Phase 1: Extract and Test (Week 1)

1. Extract `PlaceMatcher` service
2. Extract `BurialDateCalculator` utility
3. Add unit tests for extracted components
4. Keep existing code working (parallel implementation)

### Phase 2: Create Service Layer (Week 2)

1. Create `BurialEventService`
2. Create repository interfaces
3. Migrate logic from god functions to service
4. Add integration tests

### Phase 3: Refactor UI (Week 3)

1. Update UI to use service layer
2. Remove direct database coupling
3. Simplify `_start_batch_processing`
4. Add UI component tests

### Phase 4: Clean Up (Week 4)

1. Remove old god functions
2. Update documentation
3. Run full test suite
4. Performance testing

---

## Metrics to Track

| Metric | Current | Target | Industry Standard |
|--------|---------|--------|-------------------|
| Average function size | 77 lines | <30 lines | <20 lines |
| Functions >100 lines | 10 (24%) | 0 (0%) | <5% |
| Max nesting level | 11 | 4 | 3-4 |
| Cyclomatic complexity | ~197/file | <50/file | <20/file |
| Test coverage | Good (DB) | >80% (all) | >80% |
| Test execution time | Fast | <5s unit | <10s total |

---

## Conclusion

**Current State**: The code works but is **not sustainable for long-term maintenance**.

**Main Issues:**
1. God functions (up to 406 lines)
2. Excessive complexity (197 cyclomatic complexity per file)
3. Poor separation of concerns
4. Difficult to test and modify

**Recommendation**: **Refactor before adding new features**

**Estimated Effort**: 3-4 weeks of focused refactoring

**Risk of Not Refactoring**:
- Bugs will become harder to fix
- New features will take longer to implement
- Code will become unmaintainable
- Technical debt will compound

**Benefits of Refactoring**:
- Easier to add features
- Faster debugging
- Better test coverage
- More maintainable long-term
- Easier onboarding for new developers

---

**Next Steps:**
1. Review this assessment with team
2. Prioritize which god functions to refactor first
3. Start with extracting PlaceMatcher (highest reuse potential)
4. Create refactoring branch
5. Implement Phase 1 (Extract and Test)

**Note**: The database integrity tests we added are excellent and should be maintained during refactoring. They will catch any regressions.
