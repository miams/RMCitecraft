"""Unit tests for BatchStateRepository."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from rmcitecraft.database.batch_state_repository import BatchStateRepository


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_batch_state.db"
        yield str(db_path)


@pytest.fixture
def repository(temp_db):
    """Create BatchStateRepository instance with temporary database."""
    return BatchStateRepository(db_path=temp_db)


class TestBatchStateRepository:
    """Test BatchStateRepository CRUD operations."""

    def test_initialization_creates_database(self, temp_db):
        """Test repository initialization creates database file."""
        assert not Path(temp_db).exists()

        repository = BatchStateRepository(db_path=temp_db)

        assert Path(temp_db).exists()

    def test_initialization_creates_tables(self, repository, temp_db):
        """Test repository creates all required tables."""
        import sqlite3

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Check tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            ORDER BY name
        """)

        tables = [row[0] for row in cursor.fetchall()]

        assert 'batch_sessions' in tables
        assert 'batch_items' in tables
        assert 'batch_checkpoints' in tables
        assert 'performance_metrics' in tables

        conn.close()

    def test_create_session(self, repository):
        """Test creating a new batch session."""
        session_id = "test_session_1"
        total_items = 10
        config_snapshot = {'timeout': 30, 'max_retries': 3}

        repository.create_session(session_id, total_items, config_snapshot)

        # Verify session was created
        session = repository.get_session(session_id)

        assert session is not None
        assert session['session_id'] == session_id
        assert session['total_items'] == total_items
        assert session['status'] == 'queued'
        assert session['completed_count'] == 0
        assert session['error_count'] == 0

        # Config snapshot is JSON
        config = json.loads(session['config_snapshot'])
        assert config == config_snapshot

    def test_get_session_not_found(self, repository):
        """Test get_session returns None for non-existent session."""
        session = repository.get_session("nonexistent_session")

        assert session is None

    def test_start_session(self, repository):
        """Test starting a session."""
        session_id = "test_session_1"
        repository.create_session(session_id, total_items=10)

        repository.start_session(session_id)

        session = repository.get_session(session_id)

        assert session['status'] == 'running'
        assert session['started_at'] is not None

    def test_complete_session(self, repository):
        """Test completing a session."""
        session_id = "test_session_1"
        repository.create_session(session_id, total_items=10)
        repository.start_session(session_id)

        repository.complete_session(session_id)

        session = repository.get_session(session_id)

        assert session['status'] == 'completed'
        assert session['completed_at'] is not None

    def test_pause_session(self, repository):
        """Test pausing a session."""
        session_id = "test_session_1"
        repository.create_session(session_id, total_items=10)
        repository.start_session(session_id)

        repository.pause_session(session_id)

        session = repository.get_session(session_id)

        assert session['status'] == 'paused'

    def test_update_session_counts(self, repository):
        """Test updating session completed and error counts."""
        session_id = "test_session_1"
        repository.create_session(session_id, total_items=10)

        repository.update_session_counts(session_id, completed_count=7, error_count=2)

        session = repository.get_session(session_id)

        assert session['completed_count'] == 7
        assert session['error_count'] == 2

    def test_get_resumable_sessions(self, repository):
        """Test getting list of resumable sessions."""
        # Create multiple sessions with different statuses
        repository.create_session("session_1", 10)
        repository.start_session("session_1")  # running

        repository.create_session("session_2", 10)  # queued

        repository.create_session("session_3", 10)
        repository.start_session("session_3")
        repository.complete_session("session_3")  # completed

        repository.create_session("session_4", 10)
        repository.start_session("session_4")
        repository.pause_session("session_4")  # paused

        # Get resumable sessions (running, paused, queued)
        sessions = repository.get_resumable_sessions()

        # Should include session_1 (running), session_2 (queued), session_4 (paused)
        session_ids = [s['session_id'] for s in sessions]
        assert 'session_1' in session_ids
        assert 'session_2' in session_ids
        assert 'session_4' in session_ids
        assert 'session_3' not in session_ids  # completed

    def test_create_item(self, repository):
        """Test creating a batch item."""
        session_id = "test_session_1"
        repository.create_session(session_id, total_items=1)

        item_id = repository.create_item(
            session_id=session_id,
            person_id=123,
            memorial_id="456789",
            memorial_url="https://www.findagrave.com/memorial/456789",
            person_name="John Doe",
        )

        assert item_id is not None
        assert isinstance(item_id, int)

    def test_get_session_items(self, repository):
        """Test getting items for a session."""
        session_id = "test_session_1"
        repository.create_session(session_id, total_items=3)

        # Create items
        item_id_1 = repository.create_item(
            session_id, 123, "456", "url1", "Person 1"
        )
        item_id_2 = repository.create_item(
            session_id, 124, "457", "url2", "Person 2"
        )
        item_id_3 = repository.create_item(
            session_id, 125, "458", "url3", "Person 3"
        )

        # Get all items
        items = repository.get_session_items(session_id)

        assert len(items) == 3
        assert items[0]['person_id'] == 123
        assert items[1]['person_id'] == 124
        assert items[2]['person_id'] == 125

    def test_get_session_items_filtered_by_status(self, repository):
        """Test getting items filtered by status."""
        session_id = "test_session_1"
        repository.create_session(session_id, total_items=3)

        # Create items
        item_id_1 = repository.create_item(
            session_id, 123, "456", "url1", "Person 1"
        )
        item_id_2 = repository.create_item(
            session_id, 124, "457", "url2", "Person 2"
        )
        item_id_3 = repository.create_item(
            session_id, 125, "458", "url3", "Person 3"
        )

        # Update statuses
        repository.update_item_status(item_id_1, 'complete')
        repository.update_item_status(item_id_2, 'error', error_message="Test error")
        # item_id_3 stays 'queued'

        # Get only completed items
        completed_items = repository.get_session_items(session_id, status='complete')
        assert len(completed_items) == 1
        assert completed_items[0]['person_id'] == 123

        # Get only error items
        error_items = repository.get_session_items(session_id, status='error')
        assert len(error_items) == 1
        assert error_items[0]['person_id'] == 124

        # Get only queued items
        queued_items = repository.get_session_items(session_id, status='queued')
        assert len(queued_items) == 1
        assert queued_items[0]['person_id'] == 125

    def test_update_item_status(self, repository):
        """Test updating item status."""
        session_id = "test_session_1"
        repository.create_session(session_id, total_items=1)

        item_id = repository.create_item(
            session_id, 123, "456", "url", "Person"
        )

        repository.update_item_status(item_id, 'extracting')

        items = repository.get_session_items(session_id)
        assert items[0]['status'] == 'extracting'

    def test_update_item_status_with_error(self, repository):
        """Test updating item status with error message."""
        session_id = "test_session_1"
        repository.create_session(session_id, total_items=1)

        item_id = repository.create_item(
            session_id, 123, "456", "url", "Person"
        )

        repository.update_item_status(
            item_id, 'error', error_message="Network timeout"
        )

        items = repository.get_session_items(session_id)
        assert items[0]['status'] == 'error'
        assert items[0]['error_message'] == "Network timeout"

    def test_increment_retry_count(self, repository):
        """Test incrementing retry count."""
        session_id = "test_session_1"
        repository.create_session(session_id, total_items=1)

        item_id = repository.create_item(
            session_id, 123, "456", "url", "Person"
        )

        # Increment multiple times
        new_count_1 = repository.increment_retry_count(item_id)
        new_count_2 = repository.increment_retry_count(item_id)
        new_count_3 = repository.increment_retry_count(item_id)

        assert new_count_1 == 1
        assert new_count_2 == 2
        assert new_count_3 == 3

        items = repository.get_session_items(session_id)
        assert items[0]['retry_count'] == 3

    def test_update_item_extraction(self, repository):
        """Test updating item with extracted data."""
        session_id = "test_session_1"
        repository.create_session(session_id, total_items=1)

        item_id = repository.create_item(
            session_id, 123, "456", "url", "Person"
        )

        extracted_data = {
            'name': 'John Doe',
            'birth_date': '1900-01-01',
            'death_date': '1980-12-31',
            'cemetery': 'Oak Hill Cemetery',
        }

        repository.update_item_extraction(item_id, extracted_data)

        items = repository.get_session_items(session_id)
        assert items[0]['extracted_data'] == extracted_data

    def test_update_item_citation(self, repository):
        """Test updating item with created citation IDs."""
        session_id = "test_session_1"
        repository.create_session(session_id, total_items=1)

        item_id = repository.create_item(
            session_id, 123, "456", "url", "Person"
        )

        repository.update_item_citation(
            item_id,
            citation_id=1001,
            source_id=2001,
            burial_event_id=3001
        )

        items = repository.get_session_items(session_id)
        assert items[0]['created_citation_id'] == 1001
        assert items[0]['created_source_id'] == 2001
        assert items[0]['created_burial_event_id'] == 3001

    def test_create_checkpoint(self, repository):
        """Test creating a checkpoint."""
        session_id = "test_session_1"
        repository.create_session(session_id, total_items=10)

        item_id = repository.create_item(
            session_id, 123, "456", "url", "Person"
        )

        repository.create_checkpoint(session_id, item_id, 123)

        checkpoint = repository.get_checkpoint(session_id)

        assert checkpoint is not None
        assert checkpoint['session_id'] == session_id
        assert checkpoint['last_processed_item_id'] == item_id
        assert checkpoint['last_processed_person_id'] == 123

    def test_update_checkpoint(self, repository):
        """Test updating an existing checkpoint."""
        session_id = "test_session_1"
        repository.create_session(session_id, total_items=10)

        item_id_1 = repository.create_item(
            session_id, 123, "456", "url1", "Person 1"
        )
        item_id_2 = repository.create_item(
            session_id, 124, "457", "url2", "Person 2"
        )

        # Create initial checkpoint
        repository.create_checkpoint(session_id, item_id_1, 123)

        # Update checkpoint
        repository.create_checkpoint(session_id, item_id_2, 124)

        checkpoint = repository.get_checkpoint(session_id)

        # Should be updated to second item
        assert checkpoint['last_processed_item_id'] == item_id_2
        assert checkpoint['last_processed_person_id'] == 124

    def test_get_checkpoint_not_found(self, repository):
        """Test get_checkpoint returns None if not found."""
        checkpoint = repository.get_checkpoint("nonexistent_session")

        assert checkpoint is None

    def test_record_metric(self, repository):
        """Test recording performance metric."""
        session_id = "test_session_1"
        repository.create_session(session_id, total_items=1)

        repository.record_metric(
            operation='extraction',
            duration_ms=1500,
            success=True,
            session_id=session_id
        )

        # Verify metric was recorded (no direct getter, but check via get_session_metrics)
        metrics = repository.get_session_metrics(session_id)

        assert 'extraction' in metrics
        assert metrics['extraction']['count'] == 1

    def test_get_recent_metrics(self, repository):
        """Test getting recent metrics for operation."""
        session_id = "test_session_1"
        repository.create_session(session_id, total_items=1)

        # Record multiple metrics
        for duration in [1000, 1500, 2000, 2500, 3000]:
            repository.record_metric(
                operation='extraction',
                duration_ms=duration,
                success=True,
                session_id=session_id
            )

        # Get recent metrics
        recent = repository.get_recent_metrics(
            operation='extraction',
            limit=3,
            success_only=True
        )

        # Should get last 3 durations in DESC order (most recent first)
        assert len(recent) == 3
        assert recent == [3000, 2500, 2000]

    def test_get_recent_metrics_success_only(self, repository):
        """Test get_recent_metrics filters by success."""
        session_id = "test_session_1"
        repository.create_session(session_id, total_items=1)

        # Record mix of successes and failures
        repository.record_metric('extraction', 1000, success=True, session_id=session_id)
        repository.record_metric('extraction', 2000, success=False, session_id=session_id)
        repository.record_metric('extraction', 3000, success=True, session_id=session_id)

        # Get only successful metrics
        recent = repository.get_recent_metrics(
            operation='extraction',
            limit=10,
            success_only=True
        )

        assert len(recent) == 2
        # DESC order (most recent first)
        assert recent == [3000, 1000]

    def test_get_session_metrics(self, repository):
        """Test getting aggregated session metrics."""
        session_id = "test_session_1"
        repository.create_session(session_id, total_items=1)

        # Record metrics for different operations
        repository.record_metric('extraction', 1000, success=True, session_id=session_id)
        repository.record_metric('extraction', 2000, success=True, session_id=session_id)
        repository.record_metric('extraction', 3000, success=False, session_id=session_id)

        repository.record_metric('citation_creation', 500, success=True, session_id=session_id)
        repository.record_metric('citation_creation', 600, success=True, session_id=session_id)

        metrics = repository.get_session_metrics(session_id)

        # Check extraction metrics
        assert 'extraction' in metrics
        assert metrics['extraction']['count'] == 3
        assert metrics['extraction']['avg_duration_ms'] == 2000  # (1000 + 2000 + 3000) / 3
        assert metrics['extraction']['success_rate'] == pytest.approx(2/3, rel=0.01)

        # Check citation_creation metrics
        assert 'citation_creation' in metrics
        assert metrics['citation_creation']['count'] == 2
        assert metrics['citation_creation']['avg_duration_ms'] == 550  # (500 + 600) / 2
        assert metrics['citation_creation']['success_rate'] == 1.0
