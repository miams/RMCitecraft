# Refactoring Plan: Find a Grave Batch Processing

**Status**: 📋 **PLANNED** - Not yet started
**Estimated Duration**: 3-4 weeks
**Priority**: High (before adding new features)
**Risk Level**: Medium (existing tests will catch regressions)

---

## Executive Summary

This document outlines a phased approach to refactoring the Find a Grave batch processing feature from its current monolithic structure to a clean, layered architecture.

**Goals**:
- ✅ Reduce function sizes from 400+ lines to <50 lines
- ✅ Implement proper layer separation (UI → Service → Repository)
- ✅ Improve testability (unit tests for all business logic)
- ✅ Reduce cyclomatic complexity from ~200 to <50 per file
- ✅ Maintain 100% backward compatibility during migration

**Success Criteria**:
- All existing tests pass
- New unit tests achieve >80% coverage
- Functions average <30 lines
- Max nesting ≤4 levels
- Zero architectural violations (UI → DB bypassing Service)

---

## Current State Analysis

### Architectural Violations

| Violation | Impact | Severity |
|-----------|--------|----------|
| UI directly imports database layer | Tight coupling, hard to test | 🔴 Critical |
| Business logic scattered across 3 layers | Code duplication, inconsistency | 🔴 Critical |
| God functions (400+ lines) | Hard to understand, modify, test | 🔴 Critical |
| Excessive nesting (11 levels) | Cognitive overload, bug-prone | 🟡 High |
| No domain models | Dictionaries everywhere, no type safety | 🟡 High |

### Current Import Graph

```
findagrave_batch.py (UI)
    ├─→ rmcitecraft.services.findagrave_batch
    ├─→ rmcitecraft.services.findagrave_automation
    ├─→ rmcitecraft.services.findagrave_formatter
    └─→ rmcitecraft.database.findagrave_queries ❌ VIOLATION
```

**Problem**: UI bypasses service layer and directly calls database.

### Target Architecture

```
Presentation Layer (UI)
    └─→ Application Layer (Services)
            └─→ Domain Layer (Models + Business Logic)
                    └─→ Infrastructure Layer (Repositories)
```

---

## Phased Refactoring Plan

### Phase 0: Preparation (3 days)

**Goal**: Set up infrastructure for safe refactoring

#### Tasks

1. **Create Feature Flags** ✓
   ```python
   # config/feature_flags.py
   @dataclass
   class FeatureFlags:
       use_new_burial_service: bool = False  # Toggle new vs old implementation
       use_new_place_matcher: bool = False
   ```

2. **Set Up Parallel Testing** ✓
   ```python
   # tests/test_refactoring_parity.py
   def test_old_vs_new_burial_event_creation():
       """Ensure new implementation matches old exactly."""
       old_result = old_create_burial_event(...)
       new_result = new_burial_service.create_event(...)
       assert old_result == new_result
   ```

3. **Document Current Behavior** ✓
   - Create integration tests that capture current behavior
   - Document all edge cases
   - Log all decision points

4. **Create Refactoring Branch** ✓
   ```bash
   git checkout -b refactor/clean-architecture
   ```

**Deliverables**:
- [ ] Feature flag system
- [ ] Parity tests (old vs new)
- [ ] Refactoring branch
- [ ] Edge case documentation

---

### Phase 1: Extract Domain Models (Week 1)

**Goal**: Replace dictionaries with type-safe domain models

#### 1.1 Create Core Domain Models

**New Files**:
```
src/rmcitecraft/domain/
├── __init__.py
├── burial_event.py      # BurialEvent, BurialEventResult
├── cemetery.py          # Cemetery, CemeteryLocation
├── citation.py          # Citation, CitationLink
├── place.py             # Place, PlaceMatch, PlaceResolution
└── person.py            # Person (lightweight, for reference)
```

**Example - Place Models**:
```python
# src/rmcitecraft/domain/place.py

from dataclasses import dataclass
from enum import Enum

@dataclass(frozen=True)
class CemeteryLocation:
    """Immutable cemetery location data."""
    city: str | None
    county: str | None
    state: str | None
    country: str | None

    @property
    def full_name(self) -> str:
        """Build hierarchical place name."""
        parts = [self.city, self.county, self.state, self.country]
        return ", ".join(p for p in parts if p)

    @property
    def normalized_name(self) -> str:
        """Normalized for database matching."""
        parts = []
        if self.city:
            parts.append(self.city)
        if self.county:
            # Remove "County" suffix
            county = self.county.replace(' County', '').replace(' Parish', '')
            parts.append(county)
        if self.state:
            parts.append(self.state)
        if self.country:
            # Normalize USA variants
            country = self.country
            if country in ('USA', 'US', 'U.S.A.', 'U.S.'):
                country = 'United States'
            parts.append(country)
        return ", ".join(parts)

@dataclass(frozen=True)
class PlaceMatch:
    """Result of matching a location to database."""
    place_id: int
    name: str
    similarity: float
    usage_count: int
    combined_score: float

class MatchConfidence(Enum):
    """Place match confidence level."""
    HIGH = "high"        # >95% similarity
    MEDIUM = "medium"    # 80-95% similarity
    LOW = "low"          # <80% similarity
    NONE = "none"        # No match found

@dataclass(frozen=True)
class PlaceResolution:
    """Result of resolving a cemetery location."""
    location_id: int | None
    cemetery_id: int | None
    confidence: MatchConfidence
    best_match: PlaceMatch | None
    candidates: list[PlaceMatch]
    needs_approval: bool
```

**Benefits**:
- Type-safe (catches errors at development time)
- Immutable (can't accidentally modify)
- Self-documenting (clear what fields exist)
- IDE autocomplete

#### 1.2 Migrate Existing Code to Use Models

**Before (dictionaries)**:
```python
# Fragile - typos not caught, no autocomplete
cemetery_data = {
    'city': 'Kirtland',
    'county': 'Lake',
    'state': 'Ohio',
    'country': 'United States'
}
full_name = f"{cemetery_data['city']}, {cemetery_data['county']}, ..."  # Error-prone
```

**After (domain models)**:
```python
# Type-safe, autocomplete, catches typos
cemetery = CemeteryLocation(
    city='Kirtland',
    county='Lake',
    state='Ohio',
    country='United States'
)
full_name = cemetery.full_name  # Property handles formatting
normalized = cemetery.normalized_name  # Automatic normalization
```

**Migration Strategy**:
1. Create model classes
2. Add factory methods to convert dict → model
3. Update code incrementally
4. Remove factory methods once migration complete

**Deliverables**:
- [ ] Domain model classes (8-10 models)
- [ ] Unit tests for models (property calculations, validations)
- [ ] Migration complete for 50% of dict usage

---

### Phase 2: Extract Services (Week 2)

**Goal**: Move business logic from god functions into focused services

#### 2.1 Create PlaceMatcher Service

**Purpose**: Extract all place-matching logic from 400-line god function

**New File**: `src/rmcitecraft/services/place_matcher.py`

```python
from rmcitecraft.domain.place import CemeteryLocation, PlaceMatch, PlaceResolution, MatchConfidence
from rmcitecraft.services.gazetteer import GazetteerService

class PlaceMatcher:
    """
    Service for matching Find a Grave locations to database places.

    Responsibilities:
    - Calculate similarity between locations
    - Validate with gazetteer
    - Rank candidates by combined score
    - Determine if user approval needed
    """

    def __init__(self, gazetteer: GazetteerService):
        self.gazetteer = gazetteer
        self.MATCH_THRESHOLD = 0.95  # 95% similarity required

    def find_matches(
        self,
        location: CemeteryLocation,
        candidates: list[PlaceMatch]
    ) -> PlaceResolution:
        """
        Find best matching place from candidates.

        Args:
            location: Find a Grave cemetery location
            candidates: Database place candidates

        Returns:
            PlaceResolution with best match and approval status
        """
        if not candidates:
            return PlaceResolution(
                location_id=None,
                cemetery_id=None,
                confidence=MatchConfidence.NONE,
                best_match=None,
                candidates=[],
                needs_approval=True
            )

        # Calculate combined scores
        scored_candidates = self._score_candidates(location, candidates)
        best = scored_candidates[0]

        # Determine confidence
        confidence = self._determine_confidence(best.similarity)
        needs_approval = confidence != MatchConfidence.HIGH

        return PlaceResolution(
            location_id=best.place_id if not needs_approval else None,
            cemetery_id=None,  # Will be set after cemetery creation
            confidence=confidence,
            best_match=best,
            candidates=scored_candidates[:10],  # Top 10
            needs_approval=needs_approval
        )

    def _score_candidates(
        self,
        location: CemeteryLocation,
        candidates: list[PlaceMatch]
    ) -> list[PlaceMatch]:
        """Score and rank candidates by combined score."""
        # Validate with gazetteer
        gazetteer_result = self.gazetteer.validate(location)

        # Calculate combined scores
        scored = []
        for candidate in candidates:
            combined_score = self._calculate_combined_score(
                candidate.similarity,
                candidate.usage_count,
                gazetteer_result
            )
            scored.append(PlaceMatch(
                place_id=candidate.place_id,
                name=candidate.name,
                similarity=candidate.similarity,
                usage_count=candidate.usage_count,
                combined_score=combined_score
            ))

        # Sort by combined score (highest first)
        return sorted(scored, key=lambda x: x.combined_score, reverse=True)

    def _calculate_combined_score(
        self,
        similarity: float,
        usage_count: int,
        gazetteer_result
    ) -> float:
        """Calculate weighted score from multiple factors."""
        # Implement scoring logic (extracted from god function)
        ...

    def _determine_confidence(self, similarity: float) -> MatchConfidence:
        """Determine confidence level from similarity."""
        if similarity >= 0.95:
            return MatchConfidence.HIGH
        elif similarity >= 0.80:
            return MatchConfidence.MEDIUM
        elif similarity > 0:
            return MatchConfidence.LOW
        else:
            return MatchConfidence.NONE
```

**Testing**:
```python
# tests/unit/test_place_matcher.py

def test_exact_match_returns_high_confidence():
    matcher = PlaceMatcher(mock_gazetteer)
    location = CemeteryLocation(city="Kirtland", county="Lake", state="Ohio", country="USA")
    candidates = [PlaceMatch(place_id=123, name="Kirtland, Lake, Ohio, USA", similarity=1.0, usage_count=10, combined_score=0)]

    result = matcher.find_matches(location, candidates)

    assert result.confidence == MatchConfidence.HIGH
    assert not result.needs_approval
    assert result.location_id == 123

def test_low_similarity_requires_approval():
    matcher = PlaceMatcher(mock_gazetteer)
    location = CemeteryLocation(city="Kirtland", county="Lake", state="Ohio", country="USA")
    candidates = [PlaceMatch(place_id=456, name="Cleveland, Cuyahoga, Ohio, USA", similarity=0.50, usage_count=5, combined_score=0)]

    result = matcher.find_matches(location, candidates)

    assert result.confidence == MatchConfidence.LOW
    assert result.needs_approval
    assert result.location_id is None
```

**Extracted From**: `create_burial_event_and_link_citation` (lines 645-806, ~160 lines)

#### 2.2 Create BurialEventService

**Purpose**: Orchestrate burial event creation with clean business logic

**New File**: `src/rmcitecraft/services/burial_event_service.py`

```python
from rmcitecraft.domain.burial_event import BurialEvent, BurialEventResult
from rmcitecraft.domain.cemetery import Cemetery
from rmcitecraft.repositories.burial_event_repository import BurialEventRepository
from rmcitecraft.repositories.place_repository import PlaceRepository
from rmcitecraft.services.place_matcher import PlaceMatcher

class BurialEventService:
    """
    Application service for burial event business logic.

    Responsibilities:
    - Orchestrate burial event creation workflow
    - Coordinate between repositories
    - Handle approval workflow
    - No direct database access (uses repositories)
    """

    def __init__(
        self,
        burial_repo: BurialEventRepository,
        place_repo: PlaceRepository,
        place_matcher: PlaceMatcher
    ):
        self.burial_repo = burial_repo
        self.place_repo = place_repo
        self.place_matcher = place_matcher

    async def create_burial_event(
        self,
        person_id: int,
        citation_id: int,
        cemetery: Cemetery,
        approval_callback=None
    ) -> BurialEventResult:
        """
        Create burial event with automatic place matching.

        Args:
            person_id: Person to create burial for
            citation_id: Citation to link
            cemetery: Cemetery information from Find a Grave
            approval_callback: Optional callback for user approval (async function)

        Returns:
            BurialEventResult with created event and place IDs

        Raises:
            PersonNotFoundError: If person doesn't exist
            CitationNotFoundError: If citation doesn't exist
            ApprovalRequiredError: If approval_callback not provided but needed
        """
        # 1. Check for existing burial event
        existing = self.burial_repo.find_existing_burial(person_id)
        if existing:
            return self._link_to_existing_event(existing, citation_id)

        # 2. Resolve place (with approval if needed)
        place_resolution = await self._resolve_place(
            cemetery.location,
            approval_callback
        )

        # 3. Create or find cemetery
        cemetery_id = await self._resolve_cemetery(
            cemetery,
            place_resolution.location_id
        )

        # 4. Calculate burial date
        burial_date = self._calculate_burial_date(person_id)

        # 5. Create burial event
        event_id = self.burial_repo.create_event(
            person_id=person_id,
            location_id=place_resolution.location_id,
            cemetery_id=cemetery_id,
            date=burial_date.formatted,
            sort_date=burial_date.sort_value
        )

        # 6. Link citation
        self.burial_repo.link_citation(citation_id, event_id)

        return BurialEventResult(
            burial_event_id=event_id,
            location_id=place_resolution.location_id,
            cemetery_id=cemetery_id,
            needs_approval=False
        )

    async def _resolve_place(
        self,
        location: CemeteryLocation,
        approval_callback
    ) -> PlaceResolution:
        """Resolve place with approval workflow if needed."""
        # Find candidates
        candidates = self.place_repo.find_similar_places(
            location.normalized_name,
            state_filter=location.state
        )

        # Match with scoring
        resolution = self.place_matcher.find_matches(location, candidates)

        # Handle approval if needed
        if resolution.needs_approval:
            if not approval_callback:
                raise ApprovalRequiredError(
                    f"Place match confidence {resolution.confidence.value} "
                    f"requires approval but no callback provided"
                )

            # Call approval callback (UI will show dialog)
            decision = await approval_callback(resolution)

            if decision.action == 'create_new':
                location_id = self.place_repo.create_location(location)
                return PlaceResolution(
                    location_id=location_id,
                    cemetery_id=None,
                    confidence=MatchConfidence.HIGH,
                    best_match=None,
                    candidates=[],
                    needs_approval=False
                )
            elif decision.action == 'select_existing':
                return PlaceResolution(
                    location_id=decision.selected_place_id,
                    cemetery_id=None,
                    confidence=MatchConfidence.HIGH,
                    best_match=None,
                    candidates=[],
                    needs_approval=False
                )
            else:  # abort
                raise ApprovalAbortedError("User aborted place approval")

        return resolution

    def _calculate_burial_date(self, person_id: int) -> BurialDate:
        """Calculate burial date from death date."""
        death_event = self.burial_repo.find_death_event(person_id)
        if not death_event or not death_event.date:
            return BurialDate(formatted='', sort_value=0)

        # Burial is "after" death
        return BurialDate(
            formatted=f"DA+{death_event.date}..+00000000..",
            sort_value=death_event.sort_date
        )

    # ... additional helper methods
```

**Benefits**:
- Business logic isolated (no database code)
- Easy to test with mocks
- Clear workflow orchestration
- Single Responsibility Principle

**Extracted From**: `create_burial_event_and_link_citation` (entire 406-line function)

#### 2.3 Create Repository Interfaces

**Purpose**: Abstract database access behind interfaces

**New Files**:
```
src/rmcitecraft/repositories/
├── __init__.py
├── burial_event_repository.py
├── place_repository.py
└── citation_repository.py
```

**Example**:
```python
# src/rmcitecraft/repositories/burial_event_repository.py

from abc import ABC, abstractmethod
from rmcitecraft.domain.burial_event import BurialEvent

class BurialEventRepository(ABC):
    """Repository interface for burial events."""

    @abstractmethod
    def find_existing_burial(self, person_id: int) -> BurialEvent | None:
        """Find existing burial event for person."""
        pass

    @abstractmethod
    def create_event(
        self,
        person_id: int,
        location_id: int,
        cemetery_id: int,
        date: str,
        sort_date: int
    ) -> int:
        """Create burial event record."""
        pass

    @abstractmethod
    def link_citation(self, citation_id: int, event_id: int) -> None:
        """Link citation to burial event."""
        pass

# src/rmcitecraft/repositories/sqlite_burial_repository.py

class SQLiteBurialEventRepository(BurialEventRepository):
    """SQLite implementation of burial event repository."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def find_existing_burial(self, person_id: int) -> BurialEvent | None:
        """Find existing burial event for person."""
        conn = connect_rmtree(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT EventID, PlaceID, SiteID, Date, SortDate
            FROM EventTable
            WHERE OwnerType = 0
            AND OwnerID = ?
            AND EventType = 4
        """, (person_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return BurialEvent(
            event_id=row[0],
            person_id=person_id,
            location_id=row[1],
            cemetery_id=row[2],
            date=row[3],
            sort_date=row[4]
        )
```

**Benefits**:
- Can swap database implementation
- Easy to mock for testing
- Clear contract (interface)

**Deliverables**:
- [ ] PlaceMatcher service with tests
- [ ] BurialEventService with tests
- [ ] Repository interfaces
- [ ] SQLite repository implementations
- [ ] Parity tests (old vs new pass)

---

### Phase 3: Update UI to Use Services (Week 3)

**Goal**: Remove direct database coupling from UI

#### 3.1 Refactor _start_batch_processing

**Before (352 lines, direct DB access)**:
```python
async def _start_batch_processing(self):
    # ... 352 lines mixing UI, business logic, database ...
    result = create_burial_event_and_link_citation(...)  # Direct DB call ❌
```

**After (30-40 lines, delegates to service)**:
```python
async def _start_batch_processing(self):
    """Orchestrate batch processing using services."""

    # Initialize services
    burial_service = BurialEventService(
        burial_repo=SQLiteBurialEventRepository(self.config.rm_database_path),
        place_repo=SQLitePlaceRepository(self.config.rm_database_path),
        place_matcher=PlaceMatcher(gazetteer_service)
    )

    for item in items_to_process:
        try:
            # Create source and citation
            citation_result = await self._create_citation(item)

            # Create cemetery model from memorial data
            cemetery = Cemetery.from_memorial_data(item.memorial_data)

            # Create burial event (service handles business logic)
            burial_result = await burial_service.create_burial_event(
                person_id=item.person_id,
                citation_id=citation_result.citation_id,
                cemetery=cemetery,
                approval_callback=self._show_place_approval_dialog  # UI callback
            )

            # Update UI
            self._update_item_status(item, 'completed')

        except ApprovalAbortedError:
            logger.info("User aborted batch processing")
            return
        except Exception as e:
            self._handle_error(item, e)
```

**Key Changes**:
- Business logic moved to service
- UI only handles presentation and user input
- Clear separation of concerns
- Easy to test UI independently

#### 3.2 Create Approval Callback Adapter

**Purpose**: Adapt UI dialog to service's approval interface

```python
async def _show_place_approval_dialog_adapter(
    self,
    resolution: PlaceResolution
) -> ApprovalDecision:
    """
    Adapter between service approval interface and UI dialog.

    Service expects: PlaceResolution → ApprovalDecision
    UI provides: BatchItem + match_info dict → decision dict
    """
    # Convert PlaceResolution (domain) to UI format
    match_info = {
        'cemetery_name': self.current_cemetery_name,  # Track during processing
        'findagrave_location': resolution.best_match.name if resolution.best_match else '',
        'candidates': [self._place_match_to_dict(c) for c in resolution.candidates],
        'gazetteer_validation': {...}  # Convert
    }

    # Show UI dialog
    decision_dict = await self._show_place_approval_dialog(
        self.current_item,  # Track during processing
        match_info
    )

    # Convert UI result to domain ApprovalDecision
    if decision_dict['action'] == 'add_new':
        return ApprovalDecision(action='create_new')
    elif decision_dict['action'] == 'select_existing':
        return ApprovalDecision(
            action='select_existing',
            selected_place_id=decision_dict['selected_place_id']
        )
    else:
        return ApprovalDecision(action='abort')
```

**Benefits**:
- Service doesn't know about UI
- UI doesn't know about service internals
- Clear adapter pattern

**Deliverables**:
- [ ] Refactored _start_batch_processing
- [ ] Approval callback adapter
- [ ] Remove all direct DB imports from UI
- [ ] UI integration tests pass

---

### Phase 4: Clean Up and Optimize (Week 4)

**Goal**: Remove old code, optimize, document

#### 4.1 Remove Old Implementations

1. **Mark old functions as deprecated** ✓
   ```python
   @deprecated("Use BurialEventService.create_burial_event instead")
   def create_burial_event_and_link_citation(...):
       """Old implementation - use BurialEventService instead."""
       ...
   ```

2. **Remove after all callsites migrated** ✓
   - Search for `create_burial_event_and_link_citation`
   - Verify no usage outside deprecated code
   - Delete old function

3. **Remove feature flags** ✓
   - Once new implementation proven stable
   - Remove toggle code

#### 4.2 Optimize Performance

1. **Add caching where appropriate** ✓
   ```python
   from functools import lru_cache

   class PlaceRepository:
       @lru_cache(maxsize=1000)
       def find_place_by_id(self, place_id: int) -> Place:
           """Cached place lookup."""
           ...
   ```

2. **Batch database operations** ✓
   - Currently: N queries for N places
   - After: 1 query with IN clause

3. **Profile and optimize hot paths** ✓

#### 4.3 Update Documentation

1. **Update architecture docs** ✓
   - Document new layer structure
   - Update diagrams
   - Add ADRs (Architecture Decision Records)

2. **Update developer guide** ✓
   - How to add new features
   - How to test services
   - How to mock repositories

3. **Add code examples** ✓
   - Common tasks
   - Testing patterns

**Deliverables**:
- [ ] Old code removed
- [ ] Performance optimizations
- [ ] Updated documentation
- [ ] All tests passing
- [ ] Code review complete

---

## Testing Strategy

### Unit Tests (New)

**Target Coverage**: >80%

```python
# Test domain models
def test_cemetery_location_normalized_name():
    loc = CemeteryLocation(city="Kirtland", county="Lake County", state="OH", country="USA")
    assert loc.normalized_name == "Kirtland, Lake, OH, United States"

# Test services (with mocks)
def test_burial_service_links_to_existing_event():
    mock_repo = Mock(BurialEventRepository)
    mock_repo.find_existing_burial.return_value = BurialEvent(event_id=123, ...)

    service = BurialEventService(burial_repo=mock_repo, ...)
    result = await service.create_burial_event(person_id=1, ...)

    assert result.burial_event_id == 123
    mock_repo.link_citation.assert_called_once()

# Test place matcher
def test_place_matcher_exact_match():
    matcher = PlaceMatcher(mock_gazetteer)
    candidates = [PlaceMatch(place_id=1, name="Kirtland, Lake, Ohio", similarity=1.0, ...)]

    resolution = matcher.find_matches(location, candidates)

    assert resolution.confidence == MatchConfidence.HIGH
    assert not resolution.needs_approval
```

### Integration Tests (Enhanced)

**Target**: Full workflow tests with real database

```python
def test_burial_event_creation_full_workflow():
    """Test entire workflow with real database."""
    # Use test database
    service = create_burial_service(test_db_path)

    # Create burial event
    result = await service.create_burial_event(...)

    # Verify in database
    conn = connect_rmtree(test_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM EventTable WHERE EventID = ?", (result.burial_event_id,))
    event = cursor.fetchone()

    assert event is not None
    assert event[1] == 4  # EventType=4 for burial
```

### Parity Tests (Critical)

**Purpose**: Ensure new implementation matches old exactly

```python
def test_new_service_matches_old_function():
    """Verify new service produces same result as old function."""
    # Old implementation
    old_result = create_burial_event_and_link_citation(
        db_path=test_db_path,
        person_id=5978,
        citation_id=14221,
        cemetery_name="Test Cemetery",
        cemetery_city="Kirtland",
        cemetery_county="Lake",
        cemetery_state="Ohio",
        cemetery_country="United States"
    )

    # New implementation
    service = create_burial_service(test_db_path)
    cemetery = Cemetery(
        name="Test Cemetery",
        location=CemeteryLocation(city="Kirtland", county="Lake", state="Ohio", country="United States")
    )
    new_result = await service.create_burial_event(
        person_id=5978,
        citation_id=14221,
        cemetery=cemetery,
        approval_callback=None  # No approval needed for >95% match
    )

    # Compare results
    assert old_result['burial_event_id'] == new_result.burial_event_id
    assert old_result['place_id'] == new_result.location_id
    assert old_result['cemetery_id'] == new_result.cemetery_id
```

---

## Risk Mitigation

### Risk 1: Breaking Existing Functionality

**Mitigation**:
- Parity tests (old vs new)
- Feature flags (can roll back instantly)
- Parallel implementation (both old and new work)
- Comprehensive integration tests

**Rollback Plan**:
```python
# If new implementation has issues, toggle feature flag
feature_flags.use_new_burial_service = False  # Back to old code
```

### Risk 2: Performance Regression

**Mitigation**:
- Performance benchmarks before/after
- Profile hot paths
- Database query analysis (ensure no N+1)

**Acceptance Criteria**:
- Batch processing time ≤ current implementation
- Memory usage ≤ current + 10%

### Risk 3: Timeline Overrun

**Mitigation**:
- Phased approach (can stop after any phase)
- Each phase delivers value independently
- Parallel work possible (models + services)

**Contingency**:
- Phase 1-2 only (still significant improvement)
- Defer Phase 4 (optimization) if needed

---

## Success Metrics

### Code Quality Metrics

| Metric | Before | Target | Measurement |
|--------|--------|--------|-------------|
| Average function size | 77 lines | <30 lines | Radon/Pylint |
| Functions >100 lines | 10 (24%) | 0 (0%) | Manual count |
| Max nesting level | 11 | 4 | Radon |
| Cyclomatic complexity/file | ~197 | <50 | Radon |
| Test coverage | 60% | >80% | pytest-cov |

### Architecture Metrics

| Metric | Before | Target | Measurement |
|--------|--------|--------|-------------|
| UI → DB coupling | Yes ❌ | No ✅ | Import analysis |
| Service layer completeness | 20% | 100% | Architecture review |
| Domain models | 0% | 100% | Code review |
| Repository pattern | 0% | 100% | Code review |

### Performance Metrics

| Metric | Before | Target | Measurement |
|--------|--------|--------|-------------|
| Batch processing time | Baseline | ≤Baseline | Timer |
| Memory usage | Baseline | ≤Baseline+10% | Profiler |
| Test execution time | Baseline | <5s unit | pytest |

---

## Resource Requirements

### Development Time

| Phase | Duration | Resources |
|-------|----------|-----------|
| Phase 0: Preparation | 3 days | 1 developer |
| Phase 1: Domain Models | 1 week | 1 developer |
| Phase 2: Services | 1 week | 1-2 developers (parallel possible) |
| Phase 3: UI Update | 1 week | 1 developer |
| Phase 4: Clean Up | 1 week | 1 developer |
| **Total** | **3-4 weeks** | **1-2 developers** |

### Code Review

- Architecture review after Phase 1, 2
- Full code review before Phase 4
- Pair programming for critical sections

---

## Approval and Sign-Off

### Phase Approval

Each phase requires:
- [ ] All tests passing
- [ ] Code review approval
- [ ] Performance benchmarks acceptable
- [ ] Documentation updated

### Final Sign-Off

Before removing old code:
- [ ] New implementation deployed to production
- [ ] Monitoring shows no issues (1 week)
- [ ] All stakeholders approve
- [ ] Rollback plan tested

---

## Next Steps

1. **Review this plan** with team/stakeholders
2. **Approve or adjust** scope and timeline
3. **Create Phase 0 tasks** in project tracker
4. **Schedule kickoff** meeting
5. **Begin Phase 0** (preparation)

---

**Document Version**: 1.0
**Last Updated**: 2025-11-17
**Status**: Awaiting Approval
**Owner**: Development Team
