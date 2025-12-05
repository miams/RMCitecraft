---
priority: reference
topics: [database, census, citation, batch, findagrave]
---

# Test Gap Analysis

## Executive Summary

This document identifies automated unit and functional tests needed to improve test coverage for RMCitecraft. The analysis focuses on recent features (Find a Grave image download, LLM providers) and critical paths with insufficient coverage.

**Current Status:**
- 169 tests collected (1 collection error)
- Test coverage concentrated in citation parsing/formatting
- Recent features have minimal or mocked-only testing
- Integration tests exist but need expansion

---

## 1. CRITICAL: Fix Broken Tests

### Test Collection Error

**File:** `tests/unit/test_findagrave_queries.py`

**Issue:** Importing non-existent functions `_build_source_fields_xml` and `_build_citation_fields_xml`

**Impact:** Test collection fails, blocking test execution

**Fix Required:**
```python
# Remove or update these imports (lines 6-11)
from rmcitecraft.database.findagrave_queries import (
    find_findagrave_people,
    _extract_memorial_id,
    # _build_source_fields_xml,  # REMOVE - doesn't exist
    # _build_citation_fields_xml,  # REMOVE - doesn't exist
)
```

**Priority:** P0 (blocks test suite)

---

## 2. Find a Grave Image Download (Recently Added)

### Current Coverage

**File:** `tests/test_findagrave_image_workflow.py`
- ✅ Path conversion (symbolic format)
- ⚠️  Database integration (dry run only)
- ⚠️  Metadata extraction (simulation only)
- ⚠️  Workflow (commented steps, no actual execution)

### Missing Unit Tests

#### 2.1 `create_findagrave_image_record()` - Database Operations

**Location:** `src/rmcitecraft/database/findagrave_queries.py:1123`

**Tests Needed:**
```python
class TestCreateFindAGraveImageRecord:
    """Test image record creation in database."""

    def test_creates_media_record_with_correct_fields(self, test_db):
        """Verify MultimediaTable record created with all required fields."""
        # Test: MediaType=1, MediaPath=symbolic, Caption=formatted

    def test_creates_media_link_to_citation(self, test_db):
        """Verify MediaLinkTable record links to citation (OwnerType=4)."""

    def test_handles_missing_memorial_id(self, test_db):
        """Verify graceful handling when memorial_id is empty."""

    def test_handles_missing_contributor(self, test_db):
        """Verify caption generation without contributor name."""

    def test_returns_media_and_link_ids(self, test_db):
        """Verify return value contains media_id and media_link_id."""

    def test_uses_transaction_for_atomicity(self, test_db):
        """Verify rollback if any operation fails."""

    def test_path_conversion_with_spaces(self, test_db):
        """Verify filename with spaces handled correctly."""
```

**Priority:** P0 (new feature, database writes)

#### 2.2 `convert_path_to_rootsmagic_format()` - Path Conversion

**Location:** `src/rmcitecraft/database/findagrave_queries.py:1084`

**Tests Needed:**
```python
class TestConvertPathToRootsMagicFormat:
    """Test path conversion to symbolic format."""

    def test_converts_media_root_path_to_question_mark(self):
        """Verify paths under media_root use ?/ prefix."""

    def test_converts_home_path_to_tilde(self):
        """Verify paths under home use ~/ prefix."""

    def test_returns_absolute_for_other_paths(self):
        """Verify paths outside media/home remain absolute."""

    def test_handles_nested_subdirectories(self):
        """Verify deep paths converted correctly."""

    def test_preserves_forward_slashes_posix(self):
        """Verify POSIX path separators in output."""

    def test_handles_symlinks(self):
        """Verify symlinks resolved before conversion."""
```

**Priority:** P1 (critical for database integrity)

#### 2.3 UI Download Integration

**Location:** `src/rmcitecraft/ui/tabs/findagrave_batch.py:548-582`

**Tests Needed:**
```python
class TestFindAGraveBatchImageDownload:
    """Test image download UI integration."""

    def test_download_photo_creates_database_record(self, mock_browser):
        """Verify successful download creates database record."""

    def test_download_photo_tracks_media_id(self, mock_browser):
        """Verify downloaded_images stores media_id and photo_type."""

    def test_download_photo_handles_missing_citation(self, mock_browser):
        """Verify graceful handling when citation_id is None."""

    def test_download_photo_handles_database_error(self, mock_browser):
        """Verify error notification when database write fails."""

    def test_download_summary_displays_all_images(self, mock_session):
        """Verify batch summary shows all downloaded images."""

    def test_download_summary_groups_by_type(self, mock_session):
        """Verify summary counts by photo type (Person, Grave, etc)."""
```

**Priority:** P1 (UI integration, user-facing)

### Missing Integration Tests

#### 2.4 End-to-End Image Download Workflow

**Tests Needed:**
```python
class TestImageDownloadWorkflow:
    """Integration test for complete image download workflow."""

    @pytest.mark.integration
    def test_complete_workflow_with_test_db(self, test_db_path):
        """Test: Load citation → Download image → Verify database records."""
        # 1. Create test citation in database
        # 2. Trigger download (mocked browser)
        # 3. Verify MultimediaTable record
        # 4. Verify MediaLinkTable record
        # 5. Verify file written to correct directory
        # 6. Verify symbolic path format

    @pytest.mark.integration
    def test_batch_download_multiple_images(self, test_db_path):
        """Test downloading multiple images for same person."""
        # Verify: All images linked, no duplicates, correct types

    @pytest.mark.integration
    def test_download_with_existing_media_record(self, test_db_path):
        """Test behavior when image already exists in database."""
        # Verify: No duplicate, update existing, or skip
```

**Priority:** P1 (validates critical path)

---

## 3. LLM Provider System (Recently Added)

### Current Coverage

**File:** `tests/test_llm_providers.py`
- ✅ Provider factory
- ✅ OpenRouter provider (mocked)
- ✅ LLM Datasette provider (mocked)
- ✅ Photo classifier (mocked)
- ✅ Census transcriber (mocked)

**Gap:** All tests use mocks - **no actual LLM API testing**

### Missing Integration Tests

#### 3.1 Real Provider Testing (Optional but Valuable)

**Tests Needed:**
```python
@pytest.mark.integration
@pytest.mark.requires_api_key
class TestOpenRouterProviderIntegration:
    """Integration tests with real OpenRouter API."""

    def test_classify_photo_with_real_api(self):
        """Test photo classification with actual API call."""
        # Skip if OPENROUTER_API_KEY not set
        # Use test image from fixtures
        # Verify response structure and confidence

    def test_transcribe_census_with_real_api(self):
        """Test census transcription with actual API call."""
        # Use test census image from fixtures
        # Verify extracted fields match expected schema
```

**Priority:** P3 (valuable for validation, but optional)

#### 3.2 Provider Configuration and Error Handling

**Tests Needed:**
```python
class TestProviderConfiguration:
    """Test provider configuration and initialization."""

    def test_missing_api_key_raises_configuration_error(self):
        """Verify ConfigurationError when API key missing."""

    def test_invalid_provider_name_raises_error(self):
        """Verify error when unknown provider requested."""

    def test_default_provider_from_env(self):
        """Verify DEFAULT_LLM_PROVIDER environment variable used."""

    def test_fallback_to_llm_datasette(self):
        """Verify fallback when preferred provider unavailable."""
```

**Priority:** P2 (error handling critical)

#### 3.3 Photo Classifier Edge Cases

**Tests Needed:**
```python
class TestPhotoClassifierEdgeCases:
    """Test photo classifier with edge cases."""

    def test_classify_non_existent_image(self):
        """Verify FileNotFoundError for missing image."""

    def test_classify_corrupted_image(self):
        """Verify graceful handling of corrupted image file."""

    def test_classify_unsupported_format(self):
        """Verify handling of non-image files."""

    def test_suggest_photo_type_with_empty_description(self):
        """Verify fallback to 'Other' for empty descriptions."""

    def test_suggest_photo_type_case_insensitive(self):
        """Verify keyword matching is case-insensitive."""
```

**Priority:** P2 (robustness)

---

## 4. Find a Grave Automation Improvements (Recent Changes)

### Current Coverage

**Gap:** No tests for recent changes (veteran symbol cleanup, family data extraction)

### Missing Unit Tests

#### 4.1 Veteran Symbol Cleanup

**Location:** `src/rmcitecraft/services/findagrave_automation.py:208`

**Tests Needed:**
```python
class TestVeteranSymbolCleanup:
    """Test veteran symbol removal from person names."""

    def test_removes_veteran_symbol_text(self):
        """Verify ' VVeteran' removed from name."""
        # Input: "John Doe VVeteran"
        # Expected: "John Doe"

    def test_handles_multiple_spaces(self):
        """Verify whitespace variations handled."""
        # Test: "John  VVeteran Doe" → "John Doe"

    def test_preserves_name_without_symbol(self):
        """Verify names without symbol unchanged."""
        # Input: "John Doe"
        # Expected: "John Doe" (unchanged)
```

**Priority:** P2 (data quality)

#### 4.2 Family Data Extraction

**Location:** `src/rmcitecraft/services/findagrave_automation.py:385`

**Tests Needed:**
```python
class TestFamilyDataExtraction:
    """Test family data extraction for citation linking."""

    def test_extracts_family_data_from_source_comment(self):
        """Verify family dict returned with comment text."""
        # Verify tuple return: (str, dict)
        # Verify dict contains 'family' key

    def test_family_data_includes_parents(self):
        """Verify parent relationships extracted."""
        # Check for father, mother in family dict

    def test_family_data_includes_spouse(self):
        """Verify spouse relationships extracted."""
        # Check for spouse in family dict

    def test_handles_missing_family_data(self):
        """Verify empty dict when no family data found."""
        # Return: ("comment text", {})
```

**Priority:** P2 (new functionality)

---

## 5. Database Integrity Testing

### Current Coverage

**File:** `tests/unit/test_database_integrity.py` (926 lines)
- ✅ PlaceTable integrity
- ✅ SourceTable integrity
- ✅ CitationTable integrity
- ✅ EventTable integrity

### Missing Tests

#### 5.1 MultimediaTable Integrity

**Tests Needed:**
```python
class TestMultimediaTableIntegrity:
    """Test MultimediaTable record integrity."""

    def test_schema_columns_exist(self, db_connection):
        """Verify expected columns present."""
        # MediaID, MediaType, MediaPath, MediaFile, Caption, etc.

    def test_media_record_matches_existing_pattern(self, db_connection):
        """Compare created record with existing records."""
        # Field-by-field comparison

    def test_no_null_integer_columns(self, db_connection):
        """Verify integer columns use 0, not NULL."""

    def test_media_type_values(self, db_connection):
        """Verify MediaType: 1=Image, 2=File, 3=Sound, 4=Video."""

    def test_symbolic_path_format(self, db_connection):
        """Verify MediaPath uses ?/ or ~/ prefix."""
```

**Priority:** P0 (database writes, corruption risk)

#### 5.2 MediaLinkTable Integrity

**Tests Needed:**
```python
class TestMediaLinkTableIntegrity:
    """Test MediaLinkTable linking integrity."""

    def test_schema_columns_exist(self, db_connection):
        """Verify MediaID, OwnerType, OwnerID columns."""

    def test_media_link_to_citation(self, db_connection):
        """Verify OwnerType=4 for citation links."""

    def test_media_link_to_event(self, db_connection):
        """Verify OwnerType=2 for event links."""

    def test_foreign_key_validity(self, db_connection):
        """Verify MediaID references valid MultimediaTable record."""

    def test_owner_id_validity(self, db_connection):
        """Verify OwnerID references valid record in owner table."""
```

**Priority:** P0 (database relationships)

---

## 6. Browser Automation (Playwright)

### Current Coverage

**File:** `tests/e2e/test_chrome_connection.py`
- ✅ Chrome connection
- ⚠️  Basic connectivity only

**File:** `tests/e2e/test_complete_workflow.py`
- ✅ End-to-end workflow tests
- ⚠️  May be outdated

### Missing Tests

#### 6.1 Find a Grave Page Scraping

**Tests Needed:**
```python
class TestFindAGravePageScraping:
    """Test Find a Grave page data extraction."""

    @pytest.mark.e2e
    async def test_extract_person_name_with_veteran_symbol(self, page):
        """Verify veteran symbol removed from extracted name."""

    @pytest.mark.e2e
    async def test_extract_burial_date_formats(self, page):
        """Test various burial date format parsing."""

    @pytest.mark.e2e
    async def test_extract_cemetery_location(self, page):
        """Verify cemetery location extracted correctly."""

    @pytest.mark.e2e
    async def test_extract_family_members(self, page):
        """Verify family relationships extracted."""

    @pytest.mark.e2e
    async def test_extract_photo_metadata(self, page):
        """Verify photo contributor and type extracted."""
```

**Priority:** P2 (scraping reliability)

---

## 7. Error Handling and Edge Cases

### Missing Tests Across Modules

#### 7.1 Database Connection Errors

**Tests Needed:**
```python
class TestDatabaseErrorHandling:
    """Test database error handling."""

    def test_handles_missing_database_file(self):
        """Verify error when database file doesn't exist."""

    def test_handles_corrupted_database(self):
        """Verify error when database corrupted."""

    def test_handles_read_only_database(self):
        """Verify error when write attempted on read-only DB."""

    def test_handles_icu_extension_missing(self):
        """Verify error when ICU extension not found."""

    def test_handles_rmnocase_collation_failure(self):
        """Verify error when RMNOCASE collation fails."""
```

**Priority:** P1 (robustness)

#### 7.2 File System Errors

**Tests Needed:**
```python
class TestFileSystemErrorHandling:
    """Test file system error handling."""

    def test_handles_permission_denied(self):
        """Verify error when insufficient permissions."""

    def test_handles_disk_full(self):
        """Verify error when disk space exhausted."""

    def test_handles_path_too_long(self):
        """Verify error when path exceeds OS limit."""

    def test_handles_invalid_characters_in_filename(self):
        """Verify sanitization of illegal characters."""
```

**Priority:** P2 (edge cases)

---

## 8. Configuration and Environment

### Missing Tests

#### 8.1 Environment Variable Handling

**Tests Needed:**
```python
class TestConfigurationLoading:
    """Test configuration from environment."""

    def test_loads_from_env_file(self):
        """Verify .env file parsed correctly."""

    def test_handles_missing_env_file(self):
        """Verify defaults used when .env missing."""

    def test_validates_required_settings(self):
        """Verify error when required settings missing."""

    def test_validates_path_settings_exist(self):
        """Verify error when configured paths don't exist."""
```

**Priority:** P2 (startup reliability)

---

## 9. Performance and Concurrency

### Missing Tests

#### 9.1 Batch Processing Performance

**Tests Needed:**
```python
class TestBatchProcessingPerformance:
    """Test batch processing performance."""

    @pytest.mark.slow
    def test_batch_process_100_citations(self):
        """Verify reasonable performance for 100 citations."""
        # Set time limit (e.g., < 60 seconds)

    @pytest.mark.slow
    def test_parallel_llm_requests(self):
        """Verify parallel LLM processing."""
        # Test 10 citations processed concurrently

    def test_database_transaction_timeout(self):
        """Verify timeout for long-running transactions."""
```

**Priority:** P3 (optimization)

---

## Test Priority Summary

### P0 - Critical (Must Fix Now)
1. Fix `test_findagrave_queries.py` import error
2. `TestCreateFindAGraveImageRecord` (database writes)
3. `TestMultimediaTableIntegrity` (database corruption risk)
4. `TestMediaLinkTableIntegrity` (database relationships)

### P1 - High Priority (Add Soon)
5. `TestConvertPathToRootsMagicFormat` (data integrity)
6. `TestFindAGraveBatchImageDownload` (UI integration)
7. `TestImageDownloadWorkflow` (integration test)
8. `TestDatabaseErrorHandling` (robustness)

### P2 - Medium Priority (Add as Time Permits)
9. `TestProviderConfiguration` (LLM error handling)
10. `TestPhotoClassifierEdgeCases` (robustness)
11. `TestVeteranSymbolCleanup` (data quality)
12. `TestFamilyDataExtraction` (new functionality)
13. `TestFindAGravePageScraping` (scraping reliability)
14. `TestFileSystemErrorHandling` (edge cases)
15. `TestConfigurationLoading` (startup reliability)

### P3 - Low Priority (Nice to Have)
16. `TestOpenRouterProviderIntegration` (real API testing)
17. `TestBatchProcessingPerformance` (optimization)

---

## Recommended Next Steps

1. **Fix broken test** (`test_findagrave_queries.py`) - blocks test suite execution
2. **Add database integrity tests** for MultimediaTable and MediaLinkTable
3. **Add unit tests** for `create_findagrave_image_record()` and path conversion
4. **Add integration test** for complete image download workflow
5. **Review and update** existing e2e tests for compatibility with recent changes

---

## Test Infrastructure Improvements

### Fixtures Needed

```python
@pytest.fixture
def test_db_with_findagrave_data(tmp_path):
    """Create test database with Find a Grave citation and event."""
    # Create minimal database with:
    # - PersonTable record
    # - SourceTable record (Find a Grave)
    # - CitationTable record
    # - EventTable record (Burial)
    # - NameTable record
    return db_path

@pytest.fixture
def mock_findagrave_page():
    """Mock Playwright page with Find a Grave HTML."""
    # Return page object with test HTML

@pytest.fixture
def test_images(tmp_path):
    """Create test image files in various formats."""
    # Return dict of test image paths
```

### Test Data Needed

- Sample Find a Grave memorial HTML (various formats)
- Sample census images (1790-1950 coverage)
- Sample photos for classification (Person, Grave, Family, etc.)
- Database snapshots with various citation types

---

**Last Updated:** 2025-11-18
