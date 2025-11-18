# Architecture Assessment: Presentation vs Application Logic Separation

**Assessment Date**: 2025-11-17
**Scope**: RMCitecraft - Find a Grave Batch Processing Feature
**Verdict**: ❌ **POOR SEPARATION** - Significant architectural violations

---

## Executive Summary

**Question**: Does the code employ a strong application architecture with good logical separation between the presentation layer and the application logic layer?

**Answer**: **No**. The current architecture violates fundamental separation of concerns principles:

- ❌ **UI directly calls database layer** (bypassing application logic)
- ❌ **Business logic scattered across all layers**
- ❌ **No domain models** (dictionaries passed between layers)
- ❌ **Tight coupling** makes testing and modification difficult

**Impact**: The code works but is difficult to maintain, test, and extend.

---

## Architectural Analysis

### What Good Architecture Looks Like

**Clean Architecture (Dependency Rule)**:
```
┌─────────────────────────────────────────┐
│  Presentation Layer (UI)                │  ← User interaction only
│  - Render views                         │
│  - Handle user input                    │
│  - Display results                      │
└────────────────┬────────────────────────┘
                 │ Depends on ↓
                 ↓
┌─────────────────────────────────────────┐
│  Application Layer (Services)           │  ← Business logic
│  - Use cases / workflows                │
│  - Orchestration                        │
│  - Business rules                       │
└────────────────┬────────────────────────┘
                 │ Depends on ↓
                 ↓
┌─────────────────────────────────────────┐
│  Domain Layer (Models)                  │  ← Core business entities
│  - Business entities                    │
│  - Value objects                        │
│  - Domain logic                         │
└────────────────┬────────────────────────┘
                 │ Depends on ↓
                 ↓
┌─────────────────────────────────────────┐
│  Infrastructure Layer (Repositories)    │  ← External services
│  - Database access                      │
│  - File system                          │
│  - External APIs                        │
└─────────────────────────────────────────┘
```

**Key Principle**: Dependencies point inward. UI depends on Services, Services depend on Domain, Domain depends on nothing.

### Current Architecture (Reality)

```
┌──────────────────────────────────────────┐
│  Presentation Layer                      │
│  findagrave_batch.py (1,194 lines)       │
│                                           │
│  Imports:                                 │
│  ├─→ services.findagrave_batch           │
│  ├─→ services.findagrave_automation      │
│  ├─→ services.findagrave_formatter       │
│  └─→ database.findagrave_queries ❌      │  VIOLATION!
│                                           │
│  Contains:                                │
│  - UI rendering                           │
│  - User input handling                    │
│  - Business logic (embedded in UI) ❌    │
│  - Direct database calls ❌              │
└────────────────┬─────────────────────────┘
                 │
                 ├─→ Service Layer (partial)
                 │   ├─→ findagrave_automation.py
                 │   ├─→ findagrave_formatter.py
                 │   └─→ findagrave_batch.py
                 │
                 └─→ Database Layer
                     └─→ findagrave_queries.py (1,379 lines)
                         - Database operations
                         - Business logic (embedded) ❌
                         - Place matching logic ❌
                         - Validation logic ❌
```

**Problems**:
1. UI bypasses Service layer and goes straight to Database
2. Business logic duplicated across UI and Database layers
3. No Domain layer (business entities)
4. Tight coupling prevents testing

---

## Critical Architectural Violations

### Violation 1: UI Layer Directly Imports Database Layer

**Evidence**: `findagrave_batch.py` line 21-27
```python
# src/rmcitecraft/ui/tabs/findagrave_batch.py

from nicegui import ui  # ✅ OK - UI imports UI framework

from rmcitecraft.database.findagrave_queries import (  # ❌ VIOLATION!
    create_findagrave_source_and_citation,
    create_burial_event_and_link_citation,
    link_citation_to_families,
    create_location_and_cemetery,
    create_cemetery_for_existing_location,
)
```

**Why This is Bad**:
- **Tight coupling**: UI can't work without specific database implementation
- **Hard to test**: Can't test UI without real database
- **Hard to change**: Changing database layer breaks UI
- **No business logic layer**: Business rules scattered in both UI and DB

**Impact**:
```python
# In UI code (findagrave_batch.py)
async def _start_batch_processing(self):
    # ... UI code ...
    result = create_burial_event_and_link_citation(  # Direct DB call from UI!
        db_path=self.config.rm_database_path,
        person_id=item.person_id,
        # ... more parameters ...
    )
    # ... more UI code ...
```

**Correct Approach**:
```python
# UI should call Service, not Database
async def _start_batch_processing(self):
    # ... UI code ...
    burial_service = self.get_burial_service()  # Get service
    result = await burial_service.create_burial_event(  # Service call, not DB!
        person_id=item.person_id,
        cemetery=cemetery_data,
        # ... domain objects, not raw data ...
    )
    # ... more UI code ...
```

### Violation 2: Business Logic in Database Layer

**Evidence**: `findagrave_queries.py` contains:
- Place matching logic (should be in Service)
- Validation logic (should be in Service)
- Similarity calculations (should be in Service)
- Approval workflow logic (should be in Service)

**Example from `create_burial_event_and_link_citation` (line 645-806)**:
```python
# This is business logic, NOT database logic!
# Calculate similarity ratio
ratio = SequenceMatcher(None, location_name.lower(), compare_name.lower()).ratio()

# Validate with gazetteer (external service call from database layer!)
gazetteer_validation = validate_place_with_gazetteer(location_name)

# Calculate combined scores (business logic)
candidate['combined_score'] = calculate_combined_score(
    candidate['similarity'],
    gazetteer_validation
)

# Business decision: does this need approval?
if best_match_ratio >= 0.95:
    place_id = best_place_id  # Use existing
else:
    # Return for approval (business workflow logic)
    return {
        'burial_event_id': None,
        'needs_approval': True,
        'match_info': {...}
    }
```

**Why This is Bad**:
- Database layer should only handle data persistence
- Business logic should be in Service layer
- Can't reuse this logic elsewhere (it's buried in a 400-line function)
- Can't test business logic without database

**Where It Should Be**:
```python
# Service layer (business logic)
class PlaceMatcherService:
    def find_best_match(self, location, candidates):
        """Business logic for place matching."""
        # Calculate similarity
        # Validate with gazetteer
        # Calculate scores
        # Determine if approval needed
        # Return business decision

# Repository layer (database only)
class PlaceRepository:
    def find_similar_places(self, location_name, state):
        """Query database for similar places. NO business logic."""
        cursor.execute("SELECT ... WHERE ...")
        return cursor.fetchall()
```

### Violation 3: Business Logic in UI Layer

**Evidence**: `findagrave_batch.py` `_start_batch_processing` (352 lines) contains:
- Approval workflow logic (should be in Service)
- Place creation decisions (should be in Service)
- Error handling strategy (should be in Service)

**Example** (line 915-940):
```python
# In UI code - this is business logic!
if decision['action'] == 'add_new':
    # Create new location and cemetery
    place_result = create_location_and_cemetery(...)  # Business decision in UI
    location_id = place_result['location_id']
    cemetery_id = place_result['cemetery_id']

    # Re-run burial event creation
    burial_result_retry = create_burial_event_and_link_citation(...)  # Business workflow in UI
    burial_event_id = burial_result_retry['burial_event_id']

elif decision['action'] == 'select_existing':
    # Use selected existing location
    cemetery_id = create_cemetery_for_existing_location(...)  # Business decision in UI

    # Now create burial event
    burial_result_retry = create_burial_event_and_link_citation(...)
    burial_event_id = burial_result_retry['burial_event_id']
```

**Why This is Bad**:
- UI should only handle presentation and user input
- Business decisions (create new vs use existing) should be in Service
- Workflow orchestration (create, retry, link) should be in Service
- Can't reuse this logic outside the UI

### Violation 4: No Domain Models

**Evidence**: Data passed as dictionaries everywhere

**Example**:
```python
# Returning untyped dictionary from database layer
return {
    'burial_event_id': burial_event_id,
    'place_id': place_id,
    'cemetery_id': cemetery_id,
    'needs_approval': False,
    'match_info': {
        'cemetery_name': cemetery_name,
        'findagrave_location': location_name,
        # ... more nested dictionaries
    },
}

# UI receives dictionary - no type safety
result = create_burial_event_and_link_citation(...)
burial_id = result['burial_event_id']  # Typo not caught!
needs_approval = result['needs_approvel']  # Typo! Runtime error!
```

**Problems**:
- No type safety (typos not caught until runtime)
- No IDE autocomplete
- Unclear what fields exist
- Hard to refactor
- No validation

**Correct Approach**:
```python
# Domain model (type-safe)
@dataclass(frozen=True)
class BurialEventResult:
    burial_event_id: int
    location_id: int
    cemetery_id: int
    needs_approval: bool

# Service returns domain model
def create_burial_event(...) -> BurialEventResult:
    return BurialEventResult(
        burial_event_id=123,
        location_id=456,
        cemetery_id=789,
        needs_approval=False
    )

# UI receives typed object
result = create_burial_event(...)
burial_id = result.burial_event_id  # Autocomplete! Type-safe!
needs_approval = result.needs_approval  # Typo caught at development time!
```

---

## Layer Responsibility Analysis

### Current State (Violates SRP)

| Layer | Current Responsibilities | Should Have |
|-------|-------------------------|-------------|
| **UI** | - Rendering ✅<br>- User input ✅<br>- Business logic ❌<br>- Database calls ❌<br>- Workflow orchestration ❌ | - Rendering<br>- User input<br>- Display results |
| **Service** | - Data transformation ✅<br>- Some business logic ✅ | - All business logic<br>- Workflow orchestration<br>- Use cases |
| **Domain** | - Does not exist ❌ | - Business entities<br>- Business rules<br>- Validations |
| **Database** | - Database access ✅<br>- Business logic ❌<br>- Validation ❌<br>- Approval workflow ❌ | - Database access only<br>- No business logic |

### Example: Place Approval Workflow

**Current**: Logic scattered across 3 layers

```
┌─────────────────────────────────────┐
│ UI Layer (findagrave_batch.py)      │
│ - Decides when to show approval ❌  │
│ - Handles approval result ❌        │
│ - Creates location if approved ❌   │
└──────────────┬──────────────────────┘
               │ Calls
               ↓
┌─────────────────────────────────────┐
│ Database (findagrave_queries.py)    │
│ - Calculates if approval needed ❌  │
│ - Returns approval info ❌          │
│ - Creates location (in UI!) ❌     │
└─────────────────────────────────────┘
```

**Correct**: Single responsibility per layer

```
┌─────────────────────────────────────┐
│ UI Layer                             │
│ - Shows approval dialog ✅          │
│ - Returns user's choice ✅          │
└──────────────┬──────────────────────┘
               │ Callback
               ↑
┌──────────────┴──────────────────────┐
│ Service Layer                        │
│ - Orchestrates approval workflow ✅ │
│ - Makes business decisions ✅       │
│ - Calls repository for data ✅      │
└──────────────┬──────────────────────┘
               │ Uses
               ↓
┌─────────────────────────────────────┐
│ Repository Layer                     │
│ - Creates location record ✅        │
│ - Queries database ✅               │
└─────────────────────────────────────┘
```

---

## Testing Impact

### Current Architecture

**Can't unit test**:
- Can't test place matching without database
- Can't test UI without database
- Can't test approval workflow in isolation

**Can only integration test**:
```python
# Can only test the entire 400-line function
def test_create_burial_event():
    """Requires real database, real UI, everything."""
    result = create_burial_event_and_link_citation(
        db_path=real_database,  # Need real DB
        # ... 10 parameters ...
    )
    # If it fails, where? Line 50? 200? 350?
```

### Clean Architecture

**Can unit test everything**:
```python
# Test business logic (no database)
def test_place_matcher_finds_exact_match():
    matcher = PlaceMatcher(mock_gazetteer)  # Mock external service
    candidates = [PlaceMatch(similarity=1.0, ...)]

    result = matcher.find_best_match(location, candidates)

    assert not result.needs_approval  # Business logic tested!

# Test service (no database)
def test_burial_service_creates_event():
    mock_repo = Mock(BurialEventRepository)  # Mock database
    service = BurialEventService(burial_repo=mock_repo, ...)

    result = await service.create_burial_event(...)

    mock_repo.create_event.assert_called_once()  # Verify interaction

# Test UI (no database, no business logic)
def test_ui_shows_approval_dialog():
    ui = FindAGraveBatchTab()
    resolution = PlaceResolution(needs_approval=True, ...)

    decision = await ui.show_approval_dialog(resolution)

    assert decision in ['create_new', 'select_existing', 'abort']
```

---

## Maintainability Impact

### Current Architecture

**Adding a new feature**:
1. Find the 400-line god function
2. Figure out where to add code
3. Risk breaking existing logic
4. Hard to test new code
5. No reuse (logic locked in function)

**Fixing a bug**:
1. Find which 400-line function has the bug
2. Read all 400 lines to understand context
3. Make change (hope it doesn't break other parts)
4. Can't unit test the fix
5. Deploy and pray

**Changing database**:
1. **Impossible** - UI directly calls database

### Clean Architecture

**Adding a new feature**:
1. Add method to Service (20-30 lines)
2. Write unit tests for method
3. Call from UI (3-5 lines)
4. High confidence (tested in isolation)

**Fixing a bug**:
1. Identify affected service (clear responsibility)
2. Read focused 20-30 line method
3. Make change
4. Run unit test
5. Deploy with confidence

**Changing database**:
1. Write new repository implementation
2. Swap in dependency injection
3. Services don't change (depend on interface)
4. UI doesn't change

---

## Code Quality Comparison

### Current Architecture

```python
# UI knows about database
async def _start_batch_processing(self):
    # 352 lines of mixed concerns
    result = create_burial_event_and_link_citation(  # Direct DB call ❌
        db_path=self.config.rm_database_path,  # UI knows DB path ❌
        person_id=item.person_id,
        cemetery_name=memorial_data.get('cemeteryName', ''),  # Data extraction in UI ❌
        # ... more coupling ...
    )

    if result.get('needs_approval'):  # UI handles business decision ❌
        # ... 100 lines of approval logic ...
```

**Problems**:
- UI coupled to database
- Business logic in UI
- Hard to test
- Hard to change

### Clean Architecture

```python
# UI only knows about services
async def _start_batch_processing(self):
    # 30-40 lines of orchestration
    burial_service = self.container.get(BurialEventService)  # DI ✅

    try:
        result = await burial_service.create_burial_event(  # Service call ✅
            person_id=item.person_id,
            cemetery=Cemetery.from_memorial(memorial_data),  # Domain model ✅
            approval_callback=self._handle_approval  # UI callback ✅
        )
        self._show_success(result)  # UI responsibility ✅

    except ApprovalAbortedError:
        self._handle_abort()  # UI responsibility ✅
    except BusinessError as e:
        self._show_error(e)  # UI responsibility ✅
```

**Benefits**:
- UI only handles UI concerns
- Business logic in service (testable)
- Clear separation
- Easy to change

---

## Recommendations

### Immediate Actions (Critical)

1. **Stop adding features** until architecture is fixed
   - Current foundation is unstable
   - More features = more technical debt

2. **Document architectural violations**
   - Create ADR (Architecture Decision Record)
   - Get team buy-in for refactoring

3. **Set up feature flags**
   - Prepare for parallel implementation
   - Allow safe migration

### Short-Term (1-2 weeks)

1. **Extract domain models** (Phase 1 of refactoring plan)
   - Replace dictionaries with type-safe models
   - Immediate benefit: catch bugs at development time

2. **Create service layer** (Phase 2)
   - Extract PlaceMatcher service
   - Extract BurialEventService
   - Remove business logic from UI and Database

3. **Create repository interfaces** (Phase 2)
   - Abstract database behind interfaces
   - Enable testing with mocks

### Medium-Term (3-4 weeks)

1. **Update UI to use services** (Phase 3)
   - Remove all database imports from UI
   - UI only calls services

2. **Remove old god functions** (Phase 4)
   - Delete 400-line functions
   - Verify all tests pass

3. **Optimize and document** (Phase 4)
   - Performance testing
   - Update architecture docs

### Long-Term (Ongoing)

1. **Enforce architecture rules**
   - Add linting rules (no UI → DB imports)
   - Code review checklist
   - Architecture tests

2. **Continuous improvement**
   - Refactor other features similarly
   - Build reusable components
   - Improve test coverage

---

## Conclusion

### Does the code employ strong application architecture?

**No**. The current architecture has significant issues:

| Criterion | Current State | Industry Standard |
|-----------|---------------|-------------------|
| Layer separation | ❌ Poor (UI → DB direct) | ✅ Clean (UI → Service → Repository) |
| Single Responsibility | ❌ Violated (mixed concerns) | ✅ Each layer has one job |
| Testability | ❌ Only integration tests | ✅ Unit + integration tests |
| Maintainability | ❌ Hard (400-line functions) | ✅ Easy (20-30 line functions) |
| Extensibility | ❌ Hard (tight coupling) | ✅ Easy (loose coupling) |

### Impact on Project

**Current State**:
- Works but hard to maintain
- Adding features is risky
- Testing is difficult
- Can't change database
- High cognitive load for developers

**After Refactoring** (see REFACTORING-PLAN.md):
- Easy to maintain
- Adding features is fast and safe
- Comprehensive test coverage
- Can swap implementations
- Low cognitive load

### Recommendation

**Implement the refactoring plan** in `REFACTORING-PLAN.md`:
- 3-4 weeks of focused work
- Significant long-term benefits
- Reduced technical debt
- Faster feature development
- Higher code quality

---

**Next Steps**:
1. Review this assessment with team
2. Approve refactoring plan
3. Begin Phase 0 (preparation)
4. Execute phased migration

---

**Assessment Date**: 2025-11-17
**Status**: Complete
**Recommendation**: Refactor before adding new features
**Priority**: High
**Risk of Not Refactoring**: Technical debt will compound, making future development increasingly difficult
