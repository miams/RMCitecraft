"""Functional/Integration tests for Census batch processing workflow.

These tests verify the integration between:
- CensusBatchStateRepository (state persistence)
- find_census_citations() (citation selection)
- FormattedCitationValidator (citation validation)
- BatchProcessingController (workflow orchestration)

External services (FamilySearch browser automation) are mocked.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rmcitecraft.database.batch_state_repository import FindAGraveBatchStateRepository
from rmcitecraft.database.census_batch_state_repository import CensusBatchStateRepository
from rmcitecraft.services.batch_processing import (
    BatchProcessingController,
    BatchProcessingState,
    CitationBatchItem,
    CitationStatus,
)
from rmcitecraft.validation.data_quality import (
    FormattedCitationValidator,
    is_citation_needs_processing,
)


@pytest.fixture
def temp_state_db():
    """Create temporary state database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_batch_state.db"
        yield str(db_path)


@pytest.fixture
def state_repository(temp_state_db):
    """Create initialized CensusBatchStateRepository."""
    FindAGraveBatchStateRepository(db_path=temp_state_db)
    return CensusBatchStateRepository(db_path=temp_state_db)


@pytest.fixture
def controller():
    """Create BatchProcessingController instance."""
    return BatchProcessingController()


class TestCensusBatchWorkflow:
    """Test complete census batch workflow without browser automation."""

    def test_create_session_and_items(self, state_repository):
        """Test creating a batch session with items."""
        session_id = "test_workflow_session"

        # Create session
        state_repository.create_session(
            session_id=session_id,
            total_items=3,
            census_year=1940
        )

        # Create items
        item_ids = []
        for i, person in enumerate([
            ("John", "Doe", "Ohio", "Noble"),
            ("Jane", "Smith", "Ohio", "Franklin"),
            ("Bob", "Jones", "Texas", "Harris"),
        ]):
            item_id = state_repository.create_item(
                session_id=session_id,
                person_id=1000 + i,
                person_name=f"{person[0]} {person[1]}",
                census_year=1940,
                state=person[2],
                county=person[3]
            )
            item_ids.append(item_id)

        # Verify session
        session = state_repository.get_session(session_id)
        assert session['total_items'] == 3
        assert session['census_year'] == 1940

        # Verify items
        items = state_repository.get_session_items(session_id)
        assert len(items) == 3

        # Verify distributions
        state_dist = state_repository.get_state_distribution()
        assert state_dist['Ohio'] == 2
        assert state_dist['Texas'] == 1

    def test_process_items_with_state_tracking(self, state_repository):
        """Test processing items with state updates and checkpoints."""
        session_id = "test_processing_session"

        state_repository.create_session(session_id, total_items=3, census_year=1940)

        item_ids = []
        for i in range(3):
            item_id = state_repository.create_item(
                session_id, person_id=1000 + i,
                person_name=f"Person {i}",
                census_year=1940, state="Ohio"
            )
            item_ids.append(item_id)

        # Start session
        state_repository.start_session(session_id)
        session = state_repository.get_session(session_id)
        assert session['status'] == 'running'

        # Process first item - success
        state_repository.update_item_status(item_ids[0], 'extracting')
        state_repository.update_item_extraction(item_ids[0], {'state': 'Ohio', 'ed': '95'})
        state_repository.update_item_status(item_ids[0], 'complete')
        state_repository.create_checkpoint(session_id, item_ids[0], 1000)

        # Process second item - error
        state_repository.update_item_status(item_ids[1], 'extracting')
        state_repository.update_item_status(item_ids[1], 'error', error_message="Timeout")
        state_repository.increment_retry_count(item_ids[1])

        # Process third item - success
        state_repository.update_item_status(item_ids[2], 'extracting')
        state_repository.update_item_extraction(item_ids[2], {'state': 'Ohio', 'ed': '96'})
        state_repository.update_item_status(item_ids[2], 'complete')
        state_repository.create_checkpoint(session_id, item_ids[2], 1002)

        # Complete session
        state_repository.update_session_counts(session_id, completed_count=2, error_count=1)
        state_repository.complete_session(session_id)

        # Verify final state
        session = state_repository.get_session(session_id)
        assert session['status'] == 'completed'
        assert session['completed_count'] == 2
        assert session['error_count'] == 1

        status_dist = state_repository.get_status_distribution(session_id)
        assert status_dist.get('complete', 0) == 2
        assert status_dist.get('error', 0) == 1

        # Verify checkpoint
        checkpoint = state_repository.get_checkpoint(session_id)
        assert checkpoint['last_processed_item_id'] == item_ids[2]

    def test_resume_interrupted_session(self, state_repository):
        """Test resuming an interrupted session from checkpoint."""
        session_id = "test_resume_session"

        state_repository.create_session(session_id, total_items=5, census_year=1940)

        item_ids = []
        for i in range(5):
            item_id = state_repository.create_item(
                session_id, person_id=1000 + i,
                person_name=f"Person {i}",
                census_year=1940, state="Ohio"
            )
            item_ids.append(item_id)

        state_repository.start_session(session_id)

        # Process first 2 items
        for i in range(2):
            state_repository.update_item_status(item_ids[i], 'complete')
            state_repository.create_checkpoint(session_id, item_ids[i], 1000 + i)

        # "Crash" - pause session
        state_repository.pause_session(session_id)

        # Resume - find last checkpoint
        checkpoint = state_repository.get_checkpoint(session_id)
        last_item_id = checkpoint['last_processed_item_id']

        # Get remaining items (status = 'queued')
        remaining_items = state_repository.get_session_items(session_id, status='queued')
        assert len(remaining_items) == 3

        # Continue processing
        state_repository.start_session(session_id)
        for item in remaining_items:
            state_repository.update_item_status(item['id'], 'complete')
            state_repository.create_checkpoint(session_id, item['id'], item['person_id'])

        state_repository.update_session_counts(session_id, completed_count=5, error_count=0)
        state_repository.complete_session(session_id)

        session = state_repository.get_session(session_id)
        assert session['status'] == 'completed'
        assert session['completed_count'] == 5


class TestCitationSelectionCriteria:
    """Test citation selection criteria (find_census_citations filtering)."""

    def test_exclude_processed_criteria_5_same_footnote(self):
        """Test Criterion 5: footnote == short_footnote means not processed."""
        same_text = "Some citation text"

        needs_processing = is_citation_needs_processing(
            footnote=same_text,
            short_footnote=same_text,
            bibliography=same_text,
            census_year=1940
        )

        assert needs_processing is True

    def test_exclude_processed_criteria_6_validation(self):
        """Test Criterion 6: validate citation elements."""
        # Valid processed citation
        footnote = (
            "1940 U.S. census, Noble County, Ohio, E.D. 95, sheet 3B, "
            "FamilySearch (https://familysearch.org)"
        )
        short_footnote = "1940 U.S. census, Noble Co., Ohio, sheet 3B, John Smith."
        bibliography = "1940 U.S Census. FamilySearch."

        needs_processing = is_citation_needs_processing(
            footnote, short_footnote, bibliography, 1940
        )

        assert needs_processing is False

    def test_exclude_processed_both_criteria_must_pass(self):
        """Test that both criteria must pass to exclude citation."""
        # Different footnote/short_footnote BUT invalid (missing ED for 1940)
        footnote = (
            "1940 U.S. census, Noble County, Ohio, sheet 3B, "
            "FamilySearch (https://familysearch.org)"
        )
        short_footnote = "1940 U.S. census, Noble Co., Ohio, sheet 3B."
        bibliography = "1940 U.S Census. FamilySearch."

        needs_processing = is_citation_needs_processing(
            footnote, short_footnote, bibliography, 1940
        )

        # Should need processing because ED is missing
        assert needs_processing is True


class TestBatchProcessingController:
    """Test BatchProcessingController state management."""

    def test_initial_state(self, controller):
        """Test controller initializes with no session."""
        # BatchProcessingController doesn't have a 'state' attribute
        # It manages state through the session
        assert controller.session is None

    def test_create_citation_batch_item(self):
        """Test creating CitationBatchItem dataclass."""
        item = CitationBatchItem(
            event_id=100,
            person_id=1000,
            citation_id=2000,
            source_id=3000,
            given_name="John",
            surname="Doe",
            full_name="John Doe",
            census_year=1940,
            source_name="Fed Census: 1940, Ohio, Noble",
            familysearch_url="https://familysearch.org/ark:/61903/1:1:TEST"
        )

        assert item.status == CitationStatus.QUEUED
        assert item.is_complete is False
        assert item.needs_manual_entry is False
        assert item.extracted_data == {}

    def test_citation_status_transitions(self):
        """Test citation status transitions."""
        item = CitationBatchItem(
            event_id=100,
            person_id=1000,
            citation_id=2000,
            source_id=3000,
            given_name="John",
            surname="Doe",
            full_name="John Doe",
            census_year=1940,
            source_name="Test Source",
        )

        # Initial state
        assert item.status == CitationStatus.QUEUED

        # Start extraction
        item.status = CitationStatus.EXTRACTING
        assert item.status == CitationStatus.EXTRACTING

        # Extraction complete
        item.status = CitationStatus.EXTRACTED
        assert item.status == CitationStatus.EXTRACTED

        # Complete
        item.status = CitationStatus.COMPLETE
        assert item.status == CitationStatus.COMPLETE
        assert item.is_complete is True


class TestDashboardAnalytics:
    """Test dashboard analytics queries."""

    def test_master_progress_calculation(self, state_repository):
        """Test master progress aggregates correctly."""
        # Create multiple sessions
        state_repository.create_session("s1", total_items=10, census_year=1940)
        state_repository.create_session("s2", total_items=10, census_year=1950)

        # Add items with various statuses
        for i in range(10):
            item_id = state_repository.create_item("s1", 1000 + i, f"P{i}", 1940)
            if i < 5:
                state_repository.update_item_status(item_id, 'complete')
            elif i < 8:
                state_repository.update_item_status(item_id, 'error')
            # else: stays queued

        for i in range(10):
            item_id = state_repository.create_item("s2", 2000 + i, f"P{i}", 1950)
            if i < 7:
                state_repository.update_item_status(item_id, 'complete')
            elif i < 9:
                state_repository.update_item_status(item_id, 'error')

        progress = state_repository.get_master_progress()

        assert progress['total_items'] == 20
        assert progress['completed'] == 12  # 5 + 7
        assert progress['failed'] == 5  # 3 + 2
        assert progress['pending'] == 3  # 2 + 1

    def test_year_distribution(self, state_repository):
        """Test year distribution for heatmaps."""
        state_repository.create_session("mixed", total_items=6)

        state_repository.create_item("mixed", 1, "P1", 1900, state="Ohio")
        state_repository.create_item("mixed", 2, "P2", 1910, state="Ohio")
        state_repository.create_item("mixed", 3, "P3", 1920, state="Texas")
        state_repository.create_item("mixed", 4, "P4", 1940, state="Ohio")
        state_repository.create_item("mixed", 5, "P5", 1940, state="Texas")
        state_repository.create_item("mixed", 6, "P6", 1950, state="Ohio")

        year_dist = state_repository.get_year_distribution()

        assert year_dist[1900] == 1
        assert year_dist[1910] == 1
        assert year_dist[1920] == 1
        assert year_dist[1940] == 2
        assert year_dist[1950] == 1

    def test_year_state_heatmap(self, state_repository):
        """Test year×state distribution for heatmaps."""
        state_repository.create_session("heatmap", total_items=4)

        state_repository.create_item("heatmap", 1, "P1", 1940, state="Ohio")
        state_repository.create_item("heatmap", 2, "P2", 1940, state="Texas")
        state_repository.create_item("heatmap", 3, "P3", 1950, state="Ohio")
        state_repository.create_item("heatmap", 4, "P4", 1950, state="Ohio")

        dist = state_repository.get_year_and_state_distribution()

        assert dist[(1940, "Ohio")] == 1
        assert dist[(1940, "Texas")] == 1
        assert dist[(1950, "Ohio")] == 2

    def test_performance_metrics_aggregation(self, state_repository):
        """Test performance metrics aggregation."""
        state_repository.create_session("perf_test", total_items=5)

        # Record various metrics
        state_repository.record_metric("page_load", 1000, True, "perf_test")
        state_repository.record_metric("page_load", 1500, True, "perf_test")
        state_repository.record_metric("page_load", 2000, False, "perf_test")
        state_repository.record_metric("extraction", 500, True, "perf_test")
        state_repository.record_metric("extraction", 600, True, "perf_test")

        metrics = state_repository.get_session_metrics("perf_test")

        assert "page_load" in metrics
        assert metrics["page_load"]["count"] == 3
        assert metrics["page_load"]["success_rate"] == pytest.approx(2/3, rel=0.01)

        assert "extraction" in metrics
        assert metrics["extraction"]["count"] == 2
        assert metrics["extraction"]["success_rate"] == 1.0


class TestErrorHandling:
    """Test error handling and recovery."""

    def test_item_retry_tracking(self, state_repository):
        """Test retry count tracking for failed items."""
        state_repository.create_session("retry_test", total_items=1)
        item_id = state_repository.create_item("retry_test", 1, "P1", 1940)

        # Simulate retries
        for i in range(3):
            count = state_repository.increment_retry_count(item_id)
            assert count == i + 1

        item = state_repository.get_item(item_id)
        assert item['retry_count'] == 3

    def test_error_categorization(self, state_repository):
        """Test error message categorization."""
        state_repository.create_session("error_test", total_items=4)

        items = []
        for i in range(4):
            items.append(state_repository.create_item("error_test", i, f"P{i}", 1940))

        # Set different error types
        state_repository.update_item_status(items[0], 'error', "Network timeout occurred")
        state_repository.update_item_status(items[1], 'error', "Extraction failed: no data")
        state_repository.update_item_status(items[2], 'error', "Validation error: missing ED")
        state_repository.update_item_status(items[3], 'error', "Some unknown error")

        error_dist = state_repository.get_error_distribution()

        # Should categorize errors
        assert len(error_dist) > 0
        total_errors = sum(error_dist.values())
        assert total_errors == 4
