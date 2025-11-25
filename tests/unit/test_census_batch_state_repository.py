"""Unit tests for CensusBatchStateRepository."""

import json
import tempfile
from pathlib import Path

import pytest

from rmcitecraft.database.batch_state_repository import FindAGraveBatchStateRepository
from rmcitecraft.database.census_batch_state_repository import CensusBatchStateRepository


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_batch_state.db"
        yield str(db_path)


@pytest.fixture
def repository(temp_db):
    """Create CensusBatchStateRepository instance with temporary database.

    Note: Must initialize with FindAGraveBatchStateRepository first to run migrations.
    """
    # Initialize database and run migrations (including census tables)
    FindAGraveBatchStateRepository(db_path=temp_db)
    return CensusBatchStateRepository(db_path=temp_db)


class TestCensusBatchStateRepository:
    """Test CensusBatchStateRepository CRUD operations."""

    # =========================================================================
    # Initialization Tests
    # =========================================================================

    def test_initialization_requires_existing_database(self, temp_db):
        """Test repository raises error if database doesn't exist."""
        with pytest.raises(FileNotFoundError):
            CensusBatchStateRepository(db_path=temp_db)

    def test_initialization_requires_census_tables(self, temp_db):
        """Test repository raises error if census tables don't exist."""
        # Create database without census tables
        import sqlite3
        conn = sqlite3.connect(temp_db)
        conn.execute("CREATE TABLE dummy (id INTEGER)")
        conn.close()

        with pytest.raises(RuntimeError, match="Census batch tables not found"):
            CensusBatchStateRepository(db_path=temp_db)

    def test_initialization_succeeds_with_migrations(self, repository, temp_db):
        """Test repository initializes when migrations have been run."""
        import sqlite3

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Check census tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name LIKE 'census%'
            ORDER BY name
        """)

        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        assert 'census_batch_sessions' in tables
        assert 'census_batch_items' in tables
        assert 'census_batch_checkpoints' in tables

    # =========================================================================
    # Session Tests
    # =========================================================================

    def test_create_session(self, repository):
        """Test creating a new census batch session."""
        session_id = "census_session_1"
        total_items = 10
        census_year = 1940
        config_snapshot = {'timeout': 30, 'max_retries': 3}

        repository.create_session(
            session_id=session_id,
            total_items=total_items,
            census_year=census_year,
            config_snapshot=config_snapshot
        )

        session = repository.get_session(session_id)

        assert session is not None
        assert session['session_id'] == session_id
        assert session['total_items'] == total_items
        assert session['census_year'] == census_year
        assert session['status'] == 'queued'
        assert session['completed_count'] == 0
        assert session['error_count'] == 0

        config = json.loads(session['config_snapshot'])
        assert config == config_snapshot

    def test_create_session_without_census_year(self, repository):
        """Test creating session without census year (mixed years)."""
        session_id = "census_session_mixed"
        repository.create_session(session_id=session_id, total_items=5)

        session = repository.get_session(session_id)
        assert session['census_year'] is None

    def test_get_session_not_found(self, repository):
        """Test get_session returns None for non-existent session."""
        session = repository.get_session("nonexistent_session")
        assert session is None

    def test_start_session(self, repository):
        """Test starting a session."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=10)

        repository.start_session(session_id)

        session = repository.get_session(session_id)
        assert session['status'] == 'running'
        assert session['started_at'] is not None

    def test_complete_session(self, repository):
        """Test completing a session."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=10)
        repository.start_session(session_id)

        repository.complete_session(session_id)

        session = repository.get_session(session_id)
        assert session['status'] == 'completed'
        assert session['completed_at'] is not None

    def test_pause_session(self, repository):
        """Test pausing a session."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=10)
        repository.start_session(session_id)

        repository.pause_session(session_id)

        session = repository.get_session(session_id)
        assert session['status'] == 'paused'

    def test_delete_session(self, repository):
        """Test deleting a session and all associated data."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=2, census_year=1940)

        # Create items
        item_id = repository.create_item(
            session_id=session_id,
            person_id=123,
            person_name="John Doe",
            census_year=1940,
            state="Ohio",
            county="Noble"
        )

        # Create checkpoint
        repository.create_checkpoint(session_id, item_id, 123)

        # Delete session
        repository.delete_session(session_id)

        # Verify all data is deleted
        assert repository.get_session(session_id) is None
        assert repository.get_checkpoint(session_id) is None
        assert len(repository.get_session_items(session_id)) == 0

    def test_clear_all_sessions(self, repository):
        """Test clearing all census sessions."""
        # Create multiple sessions
        repository.create_session("session_1", 5, census_year=1940)
        repository.create_session("session_2", 5, census_year=1950)

        # Create items
        repository.create_item("session_1", 123, "Person 1", 1940)
        repository.create_item("session_2", 124, "Person 2", 1950)

        # Clear all
        count = repository.clear_all_sessions()

        assert count == 2
        assert len(repository.get_all_sessions()) == 0

    def test_update_session_counts(self, repository):
        """Test updating session completed and error counts."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=10)

        repository.update_session_counts(session_id, completed_count=7, error_count=2)

        session = repository.get_session(session_id)
        assert session['completed_count'] == 7
        assert session['error_count'] == 2

    def test_get_resumable_sessions(self, repository):
        """Test getting list of resumable sessions."""
        # Create sessions with different statuses
        repository.create_session("session_1", 10)
        repository.start_session("session_1")  # running

        repository.create_session("session_2", 10)  # queued

        repository.create_session("session_3", 10)
        repository.start_session("session_3")
        repository.complete_session("session_3")  # completed

        repository.create_session("session_4", 10)
        repository.start_session("session_4")
        repository.pause_session("session_4")  # paused

        sessions = repository.get_resumable_sessions()
        session_ids = [s['session_id'] for s in sessions]

        assert 'session_1' in session_ids
        assert 'session_2' in session_ids
        assert 'session_4' in session_ids
        assert 'session_3' not in session_ids  # completed

    def test_get_all_sessions(self, repository):
        """Test getting all sessions."""
        repository.create_session("session_1", 5, census_year=1940)
        repository.create_session("session_2", 5, census_year=1950)

        sessions = repository.get_all_sessions()

        assert len(sessions) == 2

    # =========================================================================
    # Item Tests
    # =========================================================================

    def test_create_item(self, repository):
        """Test creating a census batch item."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=1)

        item_id = repository.create_item(
            session_id=session_id,
            person_id=123,
            person_name="John Doe",
            census_year=1940,
            state="Ohio",
            county="Noble"
        )

        assert item_id is not None
        assert isinstance(item_id, int)

        item = repository.get_item(item_id)
        assert item['person_id'] == 123
        assert item['person_name'] == "John Doe"
        assert item['census_year'] == 1940
        assert item['state'] == "Ohio"
        assert item['county'] == "Noble"
        assert item['status'] == 'queued'
        assert item['retry_count'] == 0

    def test_get_item_not_found(self, repository):
        """Test get_item returns None for non-existent item."""
        item = repository.get_item(99999)
        assert item is None

    def test_get_session_items(self, repository):
        """Test getting items for a session."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=3)

        repository.create_item(session_id, 123, "Person 1", 1940)
        repository.create_item(session_id, 124, "Person 2", 1940)
        repository.create_item(session_id, 125, "Person 3", 1940)

        items = repository.get_session_items(session_id)

        assert len(items) == 3
        assert items[0]['person_id'] == 123
        assert items[1]['person_id'] == 124
        assert items[2]['person_id'] == 125

    def test_get_session_items_filtered_by_status(self, repository):
        """Test getting items filtered by status."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=3)

        item_id_1 = repository.create_item(session_id, 123, "Person 1", 1940)
        item_id_2 = repository.create_item(session_id, 124, "Person 2", 1940)
        item_id_3 = repository.create_item(session_id, 125, "Person 3", 1940)

        repository.update_item_status(item_id_1, 'complete')
        repository.update_item_status(item_id_2, 'error', error_message="Test error")
        # item_id_3 stays 'queued'

        completed_items = repository.get_session_items(session_id, status='complete')
        assert len(completed_items) == 1
        assert completed_items[0]['person_id'] == 123

        error_items = repository.get_session_items(session_id, status='error')
        assert len(error_items) == 1
        assert error_items[0]['person_id'] == 124

        queued_items = repository.get_session_items(session_id, status='queued')
        assert len(queued_items) == 1
        assert queued_items[0]['person_id'] == 125

    def test_update_item_status(self, repository):
        """Test updating item status."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=1)

        item_id = repository.create_item(session_id, 123, "Person", 1940)

        repository.update_item_status(item_id, 'extracting')

        item = repository.get_item(item_id)
        assert item['status'] == 'extracting'

    def test_update_item_status_with_error(self, repository):
        """Test updating item status with error message."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=1)

        item_id = repository.create_item(session_id, 123, "Person", 1940)

        repository.update_item_status(item_id, 'error', error_message="Network timeout")

        item = repository.get_item(item_id)
        assert item['status'] == 'error'
        assert item['error_message'] == "Network timeout"

    def test_increment_retry_count(self, repository):
        """Test incrementing retry count."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=1)

        item_id = repository.create_item(session_id, 123, "Person", 1940)

        count_1 = repository.increment_retry_count(item_id)
        count_2 = repository.increment_retry_count(item_id)
        count_3 = repository.increment_retry_count(item_id)

        assert count_1 == 1
        assert count_2 == 2
        assert count_3 == 3

        item = repository.get_item(item_id)
        assert item['retry_count'] == 3

    def test_update_item_extraction(self, repository):
        """Test updating item with extracted data."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=1)

        item_id = repository.create_item(session_id, 123, "Person", 1940)

        extracted_data = {
            'state': 'Ohio',
            'county': 'Noble',
            'enumeration_district': '95',
            'sheet': '3B',
            'line': '45',
        }

        repository.update_item_extraction(item_id, extracted_data)

        item = repository.get_item(item_id)
        assert item['extracted_data'] == extracted_data
        assert item['status'] == 'extracted'

    def test_update_item_citation(self, repository):
        """Test updating item with created citation IDs."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=1)

        item_id = repository.create_item(session_id, 123, "Person", 1940)

        repository.update_item_citation(
            item_id,
            citation_id=1001,
            source_id=2001,
            event_id=3001
        )

        item = repository.get_item(item_id)
        assert item['created_citation_id'] == 1001
        assert item['created_source_id'] == 2001
        assert item['created_event_id'] == 3001
        assert item['status'] == 'created_citation'

    def test_update_item_images(self, repository):
        """Test updating item with downloaded image paths."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=1)

        item_id = repository.create_item(session_id, 123, "Person", 1940)

        image_paths = ["/path/to/image1.jpg", "/path/to/image2.jpg"]
        repository.update_item_images(item_id, image_paths)

        item = repository.get_item(item_id)
        assert item['downloaded_image_paths'] == image_paths

    # =========================================================================
    # Checkpoint Tests
    # =========================================================================

    def test_create_checkpoint(self, repository):
        """Test creating a checkpoint."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=10)

        item_id = repository.create_item(session_id, 123, "Person", 1940)

        repository.create_checkpoint(session_id, item_id, 123)

        checkpoint = repository.get_checkpoint(session_id)
        assert checkpoint is not None
        assert checkpoint['session_id'] == session_id
        assert checkpoint['last_processed_item_id'] == item_id
        assert checkpoint['last_processed_person_id'] == 123

    def test_update_checkpoint(self, repository):
        """Test updating an existing checkpoint."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=10)

        item_id_1 = repository.create_item(session_id, 123, "Person 1", 1940)
        item_id_2 = repository.create_item(session_id, 124, "Person 2", 1940)

        repository.create_checkpoint(session_id, item_id_1, 123)
        repository.create_checkpoint(session_id, item_id_2, 124)

        checkpoint = repository.get_checkpoint(session_id)
        assert checkpoint['last_processed_item_id'] == item_id_2
        assert checkpoint['last_processed_person_id'] == 124

    def test_get_checkpoint_not_found(self, repository):
        """Test get_checkpoint returns None if not found."""
        checkpoint = repository.get_checkpoint("nonexistent_session")
        assert checkpoint is None

    # =========================================================================
    # Performance Metrics Tests
    # =========================================================================

    def test_record_metric(self, repository):
        """Test recording performance metric."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=1)

        repository.record_metric(
            operation='extraction',
            duration_ms=1500,
            success=True,
            session_id=session_id
        )

        metrics = repository.get_session_metrics(session_id)
        assert 'extraction' in metrics
        assert metrics['extraction']['count'] == 1

    def test_get_recent_metrics(self, repository):
        """Test getting recent metrics for operation."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=1)

        for duration in [1000, 1500, 2000, 2500, 3000]:
            repository.record_metric('extraction', duration, True, session_id)

        recent = repository.get_recent_metrics('extraction', limit=3, success_only=True)

        assert len(recent) == 3
        assert recent == [3000, 2500, 2000]  # DESC order

    def test_get_recent_metrics_success_only(self, repository):
        """Test get_recent_metrics filters by success."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=1)

        repository.record_metric('extraction', 1000, success=True, session_id=session_id)
        repository.record_metric('extraction', 2000, success=False, session_id=session_id)
        repository.record_metric('extraction', 3000, success=True, session_id=session_id)

        recent = repository.get_recent_metrics('extraction', limit=10, success_only=True)

        assert len(recent) == 2
        assert recent == [3000, 1000]

    def test_get_session_metrics(self, repository):
        """Test getting aggregated session metrics."""
        session_id = "census_session_1"
        repository.create_session(session_id, total_items=1)

        repository.record_metric('extraction', 1000, True, session_id)
        repository.record_metric('extraction', 2000, True, session_id)
        repository.record_metric('extraction', 3000, False, session_id)

        metrics = repository.get_session_metrics(session_id)

        assert 'extraction' in metrics
        assert metrics['extraction']['count'] == 3
        assert metrics['extraction']['avg_duration_ms'] == 2000
        assert metrics['extraction']['success_rate'] == pytest.approx(2/3, rel=0.01)

    # =========================================================================
    # Dashboard Query Tests
    # =========================================================================

    def test_get_master_progress(self, repository):
        """Test getting overall progress across all sessions."""
        repository.create_session("session_1", 5, census_year=1940)

        item_1 = repository.create_item("session_1", 1, "P1", 1940)
        item_2 = repository.create_item("session_1", 2, "P2", 1940)
        item_3 = repository.create_item("session_1", 3, "P3", 1940)
        item_4 = repository.create_item("session_1", 4, "P4", 1940)
        item_5 = repository.create_item("session_1", 5, "P5", 1940)

        repository.update_item_status(item_1, 'complete')
        repository.update_item_status(item_2, 'complete')
        repository.update_item_status(item_3, 'error')
        # item_4, item_5 stay queued

        progress = repository.get_master_progress()

        assert progress['total_items'] == 5
        assert progress['completed'] == 2
        assert progress['failed'] == 1
        assert progress['pending'] == 2

    def test_get_status_distribution(self, repository):
        """Test getting status distribution."""
        repository.create_session("session_1", 3)

        item_1 = repository.create_item("session_1", 1, "P1", 1940)
        item_2 = repository.create_item("session_1", 2, "P2", 1940)
        item_3 = repository.create_item("session_1", 3, "P3", 1940)

        repository.update_item_status(item_1, 'complete')
        repository.update_item_status(item_2, 'error')

        dist = repository.get_status_distribution()

        assert dist.get('complete', 0) == 1
        assert dist.get('error', 0) == 1
        assert dist.get('queued', 0) == 1

    def test_get_status_distribution_by_session(self, repository):
        """Test getting status distribution for specific session."""
        repository.create_session("session_1", 2)
        repository.create_session("session_2", 2)

        item_1 = repository.create_item("session_1", 1, "P1", 1940)
        repository.create_item("session_2", 2, "P2", 1950)

        repository.update_item_status(item_1, 'complete')

        dist = repository.get_status_distribution(session_id="session_1")

        assert dist.get('complete', 0) == 1
        assert dist.get('queued', 0) == 0

    def test_get_year_distribution(self, repository):
        """Test getting distribution by census year."""
        repository.create_session("session_1", 4)

        repository.create_item("session_1", 1, "P1", 1940)
        repository.create_item("session_1", 2, "P2", 1940)
        repository.create_item("session_1", 3, "P3", 1950)
        repository.create_item("session_1", 4, "P4", 1950)

        dist = repository.get_year_distribution()

        assert dist.get(1940, 0) == 2
        assert dist.get(1950, 0) == 2

    def test_get_state_distribution(self, repository):
        """Test getting distribution by state."""
        repository.create_session("session_1", 3)

        repository.create_item("session_1", 1, "P1", 1940, state="Ohio")
        repository.create_item("session_1", 2, "P2", 1940, state="Ohio")
        repository.create_item("session_1", 3, "P3", 1940, state="Texas")

        dist = repository.get_state_distribution()

        assert dist.get("Ohio", 0) == 2
        assert dist.get("Texas", 0) == 1

    def test_get_county_distribution(self, repository):
        """Test getting distribution by county within a state."""
        repository.create_session("session_1", 3)

        repository.create_item("session_1", 1, "P1", 1940, state="Ohio", county="Noble")
        repository.create_item("session_1", 2, "P2", 1940, state="Ohio", county="Noble")
        repository.create_item("session_1", 3, "P3", 1940, state="Ohio", county="Franklin")

        dist = repository.get_county_distribution("Ohio")

        assert dist.get("Noble", 0) == 2
        assert dist.get("Franklin", 0) == 1

    def test_get_year_and_state_distribution(self, repository):
        """Test getting distribution by year AND state (for heatmaps)."""
        repository.create_session("session_1", 4)

        repository.create_item("session_1", 1, "P1", 1940, state="Ohio")
        repository.create_item("session_1", 2, "P2", 1940, state="Texas")
        repository.create_item("session_1", 3, "P3", 1950, state="Ohio")
        repository.create_item("session_1", 4, "P4", 1950, state="Ohio")

        dist = repository.get_year_and_state_distribution()

        assert dist.get((1940, "Ohio"), 0) == 1
        assert dist.get((1940, "Texas"), 0) == 1
        assert dist.get((1950, "Ohio"), 0) == 2

    def test_get_processing_timeline(self, repository):
        """Test getting processing timeline data."""
        repository.create_session("session_1", 2)

        item_1 = repository.create_item("session_1", 1, "Person 1", 1940)
        item_2 = repository.create_item("session_1", 2, "Person 2", 1940)

        repository.update_item_status(item_1, 'complete')
        repository.update_item_status(item_2, 'error', error_message="Test error")

        timeline = repository.get_processing_timeline()

        assert len(timeline) == 2
        # Check required fields exist
        for item in timeline:
            assert 'timestamp' in item
            assert 'person_id' in item
            assert 'full_name' in item
            assert 'status' in item

    def test_get_error_distribution(self, repository):
        """Test getting error distribution by error type."""
        repository.create_session("session_1", 4)

        item_1 = repository.create_item("session_1", 1, "P1", 1940)
        item_2 = repository.create_item("session_1", 2, "P2", 1940)
        item_3 = repository.create_item("session_1", 3, "P3", 1940)
        item_4 = repository.create_item("session_1", 4, "P4", 1940)

        repository.update_item_status(item_1, 'error', error_message="Network timeout")
        repository.update_item_status(item_2, 'error', error_message="Extraction failed")
        repository.update_item_status(item_3, 'error', error_message="Validation error")
        repository.update_item_status(item_4, 'error', error_message="Unknown issue")

        dist = repository.get_error_distribution()

        # Should categorize errors
        assert 'Network Error' in dist or 'Extraction Error' in dist or 'Unknown Error' in dist

    def test_get_photo_statistics(self, repository):
        """Test getting photo statistics."""
        repository.create_session("session_1", 2)

        item_1 = repository.create_item("session_1", 1, "P1", 1940)
        item_2 = repository.create_item("session_1", 2, "P2", 1940)

        repository.update_item_images(item_1, ["/path/image1.jpg", "/path/image2.jpg"])
        repository.update_item_images(item_2, ["/path/image3.jpg"])

        stats = repository.get_photo_statistics()

        assert stats['total_photos'] == 3
        assert stats['items_with_photos'] == 2
