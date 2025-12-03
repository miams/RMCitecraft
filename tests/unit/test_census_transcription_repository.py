"""Unit tests for CensusTranscriptionRepository."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from rmcitecraft.database.census_transcription_repository import (
    CensusTranscriptionRepository,
    ProcessedImage,
    TranscriptionItem,
)


@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_batch_state.db"


@pytest.fixture
def initialized_db(temp_db_path):
    """Create and initialize the test database with required schema."""
    # Create the database and initialize schema
    temp_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(temp_db_path))
    cursor = conn.cursor()

    # Create minimal schema for testing (from migration 001 + 004)
    cursor.executescript("""
        CREATE TABLE schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        INSERT INTO schema_version VALUES (4, datetime('now'));

        CREATE TABLE census_transcription_sessions (
            session_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            status TEXT DEFAULT 'queued',
            total_items INTEGER DEFAULT 0,
            completed_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            skipped_count INTEGER DEFAULT 0,
            edge_warning_count INTEGER DEFAULT 0,
            census_year INTEGER,
            state_filter TEXT,
            config_snapshot TEXT
        );

        CREATE TABLE census_transcription_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            rmtree_citation_id INTEGER NOT NULL,
            rmtree_person_id INTEGER,
            person_name TEXT,
            census_year INTEGER NOT NULL,
            state TEXT,
            county TEXT,
            familysearch_ark TEXT,
            image_ark TEXT,
            status TEXT DEFAULT 'queued',
            skip_reason TEXT,
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            last_attempt_at TEXT,
            census_db_person_id INTEGER,
            census_db_page_id INTEGER,
            household_extracted_count INTEGER DEFAULT 0,
            extraction_method TEXT,
            line_number INTEGER,
            first_line_flag INTEGER DEFAULT 0,
            last_line_flag INTEGER DEFAULT 0,
            edge_warning_message TEXT
        );

        CREATE TABLE processed_census_images (
            image_ark TEXT PRIMARY KEY,
            census_year INTEGER NOT NULL,
            state TEXT,
            county TEXT,
            enumeration_district TEXT,
            sheet_number TEXT,
            stamp_number TEXT,
            first_processed_at TEXT NOT NULL,
            last_processed_at TEXT,
            first_session_id TEXT,
            total_persons_extracted INTEGER DEFAULT 0,
            census_db_page_id INTEGER
        );

        CREATE TABLE census_transcription_checkpoints (
            session_id TEXT PRIMARY KEY,
            last_processed_item_id INTEGER,
            last_processed_citation_id INTEGER,
            checkpoint_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    yield temp_db_path


@pytest.fixture
def repo(initialized_db):
    """Create repository with initialized database."""
    return CensusTranscriptionRepository(db_path=str(initialized_db))


class TestSessionOperations:
    """Tests for session CRUD operations."""

    def test_create_session(self, repo):
        """Test creating a new session."""
        repo.create_session(
            session_id="test_session_001",
            total_items=10,
            census_year=1950,
            state_filter="OH",
        )

        session = repo.get_session("test_session_001")
        assert session is not None
        assert session["total_items"] == 10
        assert session["census_year"] == 1950
        assert session["state_filter"] == "OH"
        assert session["status"] == "queued"

    def test_start_session(self, repo):
        """Test starting a session."""
        repo.create_session("test_session", total_items=5)
        repo.start_session("test_session")

        session = repo.get_session("test_session")
        assert session["status"] == "running"
        assert session["started_at"] is not None

    def test_complete_session(self, repo):
        """Test completing a session."""
        repo.create_session("test_session", total_items=5)
        repo.start_session("test_session")
        repo.complete_session("test_session")

        session = repo.get_session("test_session")
        assert session["status"] == "completed"
        assert session["completed_at"] is not None

    def test_pause_session(self, repo):
        """Test pausing a session."""
        repo.create_session("test_session", total_items=5)
        repo.start_session("test_session")
        repo.pause_session("test_session")

        session = repo.get_session("test_session")
        assert session["status"] == "paused"

    def test_update_session_counts(self, repo):
        """Test updating session counts."""
        repo.create_session("test_session", total_items=10)
        repo.update_session_counts(
            "test_session",
            completed_count=5,
            error_count=2,
            skipped_count=1,
            edge_warning_count=3,
        )

        session = repo.get_session("test_session")
        assert session["completed_count"] == 5
        assert session["error_count"] == 2
        assert session["skipped_count"] == 1
        assert session["edge_warning_count"] == 3

    def test_get_resumable_sessions(self, repo):
        """Test getting resumable sessions."""
        repo.create_session("session_1", total_items=5)
        repo.create_session("session_2", total_items=5)
        repo.start_session("session_1")
        repo.complete_session("session_2")

        resumable = repo.get_resumable_sessions()
        session_ids = [s["session_id"] for s in resumable]
        assert "session_1" in session_ids
        assert "session_2" not in session_ids  # completed

    def test_delete_session(self, repo):
        """Test deleting a session."""
        repo.create_session("test_session", total_items=5)
        repo.create_item(
            session_id="test_session",
            rmtree_citation_id=100,
            rmtree_person_id=1,
            person_name="Test Person",
            census_year=1950,
            familysearch_ark="1:1:TEST",
        )

        repo.delete_session("test_session")
        assert repo.get_session("test_session") is None


class TestItemOperations:
    """Tests for item CRUD operations."""

    def test_create_item(self, repo):
        """Test creating an item."""
        repo.create_session("test_session", total_items=1)
        item_id = repo.create_item(
            session_id="test_session",
            rmtree_citation_id=12345,
            rmtree_person_id=100,
            person_name="R Lynn Ijams",
            census_year=1950,
            familysearch_ark="1:1:6XKG-DP65",
            state="IL",
            county="Franklin",
        )

        assert item_id > 0
        item = repo.get_item(item_id)
        assert item.person_name == "R Lynn Ijams"
        assert item.census_year == 1950
        assert item.familysearch_ark == "1:1:6XKG-DP65"

    def test_create_items_bulk(self, repo):
        """Test bulk item creation."""
        repo.create_session("test_session", total_items=3)
        items = [
            {
                "session_id": "test_session",
                "rmtree_citation_id": 100 + i,
                "rmtree_person_id": i,
                "person_name": f"Person {i}",
                "census_year": 1950,
                "familysearch_ark": f"1:1:TEST-{i}",
            }
            for i in range(3)
        ]

        count = repo.create_items_bulk(items)
        assert count == 3

        session_items = repo.get_session_items("test_session")
        assert len(session_items) == 3

    def test_update_item_status(self, repo):
        """Test updating item status."""
        repo.create_session("test_session", total_items=1)
        item_id = repo.create_item(
            session_id="test_session",
            rmtree_citation_id=100,
            rmtree_person_id=1,
            person_name="Test",
            census_year=1950,
            familysearch_ark="1:1:TEST",
        )

        repo.update_item_status(item_id, "error", error_message="Test error")
        item = repo.get_item(item_id)
        assert item.status == "error"
        assert item.error_message == "Test error"

    def test_update_item_extraction(self, repo):
        """Test updating item with extraction results."""
        repo.create_session("test_session", total_items=1)
        item_id = repo.create_item(
            session_id="test_session",
            rmtree_citation_id=100,
            rmtree_person_id=1,
            person_name="Test",
            census_year=1950,
            familysearch_ark="1:1:TEST",
        )

        repo.update_item_extraction(
            item_id=item_id,
            image_ark="3:1:XXXX-YYYY",
            census_db_person_id=999,
            census_db_page_id=888,
            household_extracted_count=4,
            extraction_method="table_arks",
            line_number=12,
            first_line_flag=False,
            last_line_flag=False,
        )

        item = repo.get_item(item_id)
        assert item.status == "extracted"
        assert item.image_ark == "3:1:XXXX-YYYY"
        assert item.census_db_person_id == 999
        assert item.household_extracted_count == 4
        assert item.line_number == 12

    def test_update_item_extraction_with_edge_flags(self, repo):
        """Test edge flag handling in extraction update."""
        repo.create_session("test_session", total_items=1)
        item_id = repo.create_item(
            session_id="test_session",
            rmtree_citation_id=100,
            rmtree_person_id=1,
            person_name="Test",
            census_year=1950,
            familysearch_ark="1:1:TEST",
        )

        repo.update_item_extraction(
            item_id=item_id,
            image_ark="3:1:XXXX-YYYY",
            census_db_person_id=999,
            census_db_page_id=888,
            household_extracted_count=2,
            line_number=1,
            first_line_flag=True,
            last_line_flag=False,
            edge_warning_message="Line 1: May have family on previous page",
        )

        item = repo.get_item(item_id)
        assert item.first_line_flag is True
        assert item.last_line_flag is False
        assert "previous page" in item.edge_warning_message

    def test_get_pending_items(self, repo):
        """Test getting pending items."""
        repo.create_session("test_session", total_items=3)
        id1 = repo.create_item(
            session_id="test_session",
            rmtree_citation_id=100,
            rmtree_person_id=1,
            person_name="Person 1",
            census_year=1950,
            familysearch_ark="1:1:TEST1",
        )
        id2 = repo.create_item(
            session_id="test_session",
            rmtree_citation_id=101,
            rmtree_person_id=2,
            person_name="Person 2",
            census_year=1950,
            familysearch_ark="1:1:TEST2",
        )

        # Mark one as complete
        repo.complete_item(id1)

        pending = repo.get_pending_items("test_session")
        assert len(pending) == 1
        assert pending[0].item_id == id2

    def test_get_edge_warning_items(self, repo):
        """Test getting items with edge warnings."""
        repo.create_session("test_session", total_items=2)
        id1 = repo.create_item(
            session_id="test_session",
            rmtree_citation_id=100,
            rmtree_person_id=1,
            person_name="Person 1",
            census_year=1950,
            familysearch_ark="1:1:TEST1",
        )
        id2 = repo.create_item(
            session_id="test_session",
            rmtree_citation_id=101,
            rmtree_person_id=2,
            person_name="Person 2",
            census_year=1950,
            familysearch_ark="1:1:TEST2",
        )

        # Set edge flag on first item
        repo.update_item_extraction(
            item_id=id1,
            image_ark="3:1:XXXX",
            census_db_person_id=1,
            census_db_page_id=1,
            line_number=1,
            first_line_flag=True,
        )
        repo.update_item_extraction(
            item_id=id2,
            image_ark="3:1:YYYY",
            census_db_person_id=2,
            census_db_page_id=2,
            line_number=15,
        )

        edge_items = repo.get_edge_warning_items("test_session")
        assert len(edge_items) == 1
        assert edge_items[0].item_id == id1


class TestDuplicatePrevention:
    """Tests for processed image tracking."""

    def test_is_image_processed_false(self, repo):
        """Test checking an unprocessed image."""
        assert repo.is_image_processed("3:1:NEVER-SEEN") is False

    def test_mark_and_check_image_processed(self, repo):
        """Test marking an image as processed."""
        repo.create_session("test_session", total_items=1)
        repo.mark_image_processed(
            image_ark="3:1:TEST-IMAGE",
            census_year=1950,
            state="IL",
            county="Franklin",
            enumeration_district="94-123",
            sheet_number="5",
            stamp_number="5643",
            census_db_page_id=888,
            person_count=4,
            session_id="test_session",
        )

        assert repo.is_image_processed("3:1:TEST-IMAGE") is True
        assert repo.is_image_processed("3:1:OTHER-IMAGE") is False

    def test_get_processed_image(self, repo):
        """Test getting processed image info."""
        repo.create_session("test_session", total_items=1)
        repo.mark_image_processed(
            image_ark="3:1:TEST-IMAGE",
            census_year=1950,
            state="IL",
            county="Franklin",
            enumeration_district="94-123",
            sheet_number="5",
            stamp_number="5643",
            census_db_page_id=888,
            person_count=4,
            session_id="test_session",
        )

        image = repo.get_processed_image("3:1:TEST-IMAGE")
        assert image is not None
        assert image.census_year == 1950
        assert image.state == "IL"
        assert image.enumeration_district == "94-123"
        assert image.total_persons_extracted == 4

    def test_get_processed_images_count(self, repo):
        """Test counting processed images."""
        repo.create_session("test_session", total_items=1)
        repo.mark_image_processed(
            image_ark="3:1:IMAGE-1",
            census_year=1950,
            state="IL",
            county="Franklin",
            enumeration_district="94-1",
            sheet_number="1",
            stamp_number="",
            census_db_page_id=1,
            person_count=4,
            session_id="test_session",
        )
        repo.mark_image_processed(
            image_ark="3:1:IMAGE-2",
            census_year=1950,
            state="OH",
            county="Noble",
            enumeration_district="67-1",
            sheet_number="1",
            stamp_number="",
            census_db_page_id=2,
            person_count=3,
            session_id="test_session",
        )

        assert repo.get_processed_images_count() == 2
        assert repo.get_processed_images_count(census_year=1950) == 2
        assert repo.get_processed_images_count(state="IL") == 1
        assert repo.get_processed_images_count(state="OH") == 1


class TestCheckpoints:
    """Tests for checkpoint operations."""

    def test_create_and_get_checkpoint(self, repo):
        """Test creating and retrieving checkpoints."""
        repo.create_session("test_session", total_items=10)
        repo.create_checkpoint(
            session_id="test_session",
            last_processed_item_id=5,
            last_processed_citation_id=500,
        )

        checkpoint = repo.get_checkpoint("test_session")
        assert checkpoint is not None
        assert checkpoint["last_processed_item_id"] == 5
        assert checkpoint["last_processed_citation_id"] == 500

    def test_update_checkpoint(self, repo):
        """Test updating an existing checkpoint."""
        repo.create_session("test_session", total_items=10)
        repo.create_checkpoint("test_session", 5, 500)
        repo.create_checkpoint("test_session", 8, 800)

        checkpoint = repo.get_checkpoint("test_session")
        assert checkpoint["last_processed_item_id"] == 8
        assert checkpoint["last_processed_citation_id"] == 800


class TestAnalytics:
    """Tests for analytics queries."""

    def test_get_session_summary(self, repo):
        """Test getting session summary."""
        repo.create_session("test_session", total_items=3)

        # Create items with different statuses
        id1 = repo.create_item(
            session_id="test_session",
            rmtree_citation_id=100,
            rmtree_person_id=1,
            person_name="Person 1",
            census_year=1950,
            familysearch_ark="1:1:TEST1",
        )
        id2 = repo.create_item(
            session_id="test_session",
            rmtree_citation_id=101,
            rmtree_person_id=2,
            person_name="Person 2",
            census_year=1950,
            familysearch_ark="1:1:TEST2",
        )
        id3 = repo.create_item(
            session_id="test_session",
            rmtree_citation_id=102,
            rmtree_person_id=3,
            person_name="Person 3",
            census_year=1950,
            familysearch_ark="1:1:TEST3",
        )

        repo.complete_item(id1)
        repo.update_item_status(id2, "error", error_message="Test error")

        summary = repo.get_session_summary("test_session")
        assert summary["total_items"] == 3
        assert summary["completed"] == 1
        assert summary["errors"] == 1
        assert summary["pending"] == 1

    def test_get_status_distribution(self, repo):
        """Test getting status distribution."""
        repo.create_session("test_session", total_items=3)

        for i in range(3):
            repo.create_item(
                session_id="test_session",
                rmtree_citation_id=100 + i,
                rmtree_person_id=i,
                person_name=f"Person {i}",
                census_year=1950,
                familysearch_ark=f"1:1:TEST{i}",
            )

        dist = repo.get_status_distribution("test_session")
        assert dist.get("queued", 0) == 3
