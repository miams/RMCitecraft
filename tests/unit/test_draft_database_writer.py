"""Unit tests for DraftDatabaseWriter service."""

import pytest
from pathlib import Path
import tempfile
import shutil

from rmcitecraft.services.draft_database_writer import DraftDatabaseWriter
from rmcitecraft.models.citation_data import SourceData, CitationData
from rmcitecraft.database.connection import connect_rmtree


@pytest.fixture
def test_db_path():
    """Create a temporary copy of the test database."""
    # Use the main database as a test database
    # In production tests, you'd want a dedicated test database
    original_db = Path('data/Iiams.rmtree')

    if not original_db.exists():
        pytest.skip("Test database not available")

    # Create temporary copy
    temp_dir = tempfile.mkdtemp()
    test_db = Path(temp_dir) / 'test.rmtree'
    shutil.copy(original_db, test_db)

    yield test_db

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_source_data():
    """Create sample source data."""
    fields_blob = b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?>\n<Root>\n' \
                 b'<Footnote>Test footnote</Footnote>\n' \
                 b'<ShortFootnote>Test short</ShortFootnote>\n' \
                 b'<Bibliography>Test bibliography</Bibliography>\n</Root>'

    return SourceData(
        name="Pennsylvania, World War II Draft Registration Cards, 1940-1945",
        ref_number="",
        comments="Test source for unit tests",
        bibliography='"Pennsylvania, World War II Draft Registration Cards, 1940-1945." '
                    'Database with images. FamilySearch. http://FamilySearch.org.',
        footnote_template="",
        short_footnote_template="",
        fields_blob=fields_blob,
        template_id=0
    )


@pytest.fixture
def sample_citation_data():
    """Create sample citation data."""
    fields_blob = b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?>\n<Root>\n' \
                 b'<Footnote>1940 U.S. draft registration, John Smith</Footnote>\n' \
                 b'<ShortFootnote>1940 U.S. draft reg., John Smith</ShortFootnote>\n' \
                 b'<Bibliography>Test bibliography</Bibliography>\n</Root>'

    return CitationData(
        source_id=0,  # Will be set when creating
        comments="",
        ref_number="",
        footnote="1940 U.S. draft registration, Allegheny County, Pennsylvania, John Smith",
        short_footnote="1940 U.S. draft reg., Allegheny Co., PA, John Smith",
        bibliography='"Pennsylvania, World War II Draft Registration Cards, 1940-1945." '
                    'Database with images. FamilySearch. http://FamilySearch.org.',
        fields_blob=fields_blob,
        actual_text="",
        quality=0
    )


class TestDatabaseWriterInit:
    """Test DraftDatabaseWriter initialization."""

    def test_init(self, test_db_path):
        """Test basic initialization."""
        writer = DraftDatabaseWriter(test_db_path, read_only=True)
        assert writer.db_path == test_db_path
        assert writer.read_only is True
        assert writer._conn is None

    def test_context_manager(self, test_db_path):
        """Test context manager opens and closes connection."""
        with DraftDatabaseWriter(test_db_path, read_only=True) as writer:
            assert writer.conn is not None
            # Connection should work
            cursor = writer.conn.cursor()
            cursor.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1

    def test_connection_outside_context_fails(self, test_db_path):
        """Test accessing connection outside context manager fails."""
        writer = DraftDatabaseWriter(test_db_path, read_only=True)
        with pytest.raises(RuntimeError, match="not connected"):
            _ = writer.conn


class TestVerifyPerson:
    """Test person verification methods."""

    def test_verify_person_exists(self, test_db_path):
        """Test verifying existing person."""
        with DraftDatabaseWriter(test_db_path, read_only=True) as writer:
            # Person with ID 1 should exist in test database
            assert writer.verify_person_exists(1) is True

    def test_verify_person_not_exists(self, test_db_path):
        """Test verifying non-existent person."""
        with DraftDatabaseWriter(test_db_path, read_only=True) as writer:
            # Person with very high ID should not exist
            assert writer.verify_person_exists(999999) is False

    def test_get_person_name(self, test_db_path):
        """Test getting person name."""
        with DraftDatabaseWriter(test_db_path, read_only=True) as writer:
            # Get name of person 1
            name = writer.get_person_name(1)
            assert name is not None
            assert len(name) > 0

    def test_get_person_name_not_found(self, test_db_path):
        """Test getting name of non-existent person."""
        with DraftDatabaseWriter(test_db_path, read_only=True) as writer:
            name = writer.get_person_name(999999)
            assert name is None


class TestSourceOperations:
    """Test source creation and lookup."""

    def test_create_source(self, test_db_path, sample_source_data):
        """Test creating a new source."""
        with DraftDatabaseWriter(test_db_path, read_only=False) as writer:
            # Add unique identifier to avoid conflicts
            sample_source_data.name = f"Test Source {Path(test_db_path).stem}"

            source_id, created = writer.create_or_find_source(sample_source_data)

            assert source_id > 0
            assert created is True

            # Verify source was created
            cursor = writer.conn.cursor()
            cursor.execute("""
                SELECT Name, Comments, TemplateID
                FROM SourceTable WHERE SourceID = ?
            """, (source_id,))

            result = cursor.fetchone()
            assert result is not None
            name, comments, template_id = result
            assert name == sample_source_data.name
            assert comments == sample_source_data.comments
            assert template_id == 0

    def test_create_source_read_only_fails(self, test_db_path, sample_source_data):
        """Test that creating source in read-only mode fails."""
        with DraftDatabaseWriter(test_db_path, read_only=True) as writer:
            with pytest.raises(RuntimeError, match="read-only"):
                writer.create_or_find_source(sample_source_data)

    def test_find_existing_source(self, test_db_path, sample_source_data):
        """Test finding an existing source."""
        with DraftDatabaseWriter(test_db_path, read_only=False) as writer:
            # Create source
            sample_source_data.name = f"Duplicate Test {Path(test_db_path).stem}"
            source_id1, created1 = writer.create_or_find_source(sample_source_data)
            assert created1 is True

            # Try to create again - should find existing
            source_id2, created2 = writer.create_or_find_source(sample_source_data)
            assert created2 is False
            assert source_id2 == source_id1

    def test_check_duplicate_source(self, test_db_path, sample_source_data):
        """Test duplicate source detection."""
        with DraftDatabaseWriter(test_db_path, read_only=False) as writer:
            # Initially no duplicate
            sample_source_data.name = f"Check Dup {Path(test_db_path).stem}"
            dup_id = writer.check_duplicate_source(sample_source_data)
            assert dup_id is None

            # Create source
            source_id, _ = writer.create_or_find_source(sample_source_data)

            # Now should find duplicate
            dup_id = writer.check_duplicate_source(sample_source_data)
            assert dup_id == source_id

    def test_get_source_citations_count(self, test_db_path):
        """Test getting citation count for a source."""
        with DraftDatabaseWriter(test_db_path, read_only=True) as writer:
            # Source 1 should exist
            count = writer.get_source_citations_count(1)
            assert count >= 0


class TestCitationOperations:
    """Test citation creation and linking."""

    def test_create_citation(self, test_db_path, sample_source_data, sample_citation_data):
        """Test creating a citation."""
        with DraftDatabaseWriter(test_db_path, read_only=False) as writer:
            # First create a source
            sample_source_data.name = f"Citation Test Source {Path(test_db_path).stem}"
            source_id, _ = writer.create_or_find_source(sample_source_data)

            # Create citation
            sample_citation_data.source_id = source_id
            citation_id = writer.create_citation(sample_citation_data)

            assert citation_id > 0

            # Verify citation was created
            cursor = writer.conn.cursor()
            cursor.execute("""
                SELECT SourceID, Footnote, ShortFootnote
                FROM CitationTable WHERE CitationID = ?
            """, (citation_id,))

            result = cursor.fetchone()
            assert result is not None
            cit_source_id, footnote, short_footnote = result
            assert cit_source_id == source_id
            assert footnote == sample_citation_data.footnote
            assert short_footnote == sample_citation_data.short_footnote

    def test_create_citation_read_only_fails(self, test_db_path, sample_citation_data):
        """Test that creating citation in read-only mode fails."""
        with DraftDatabaseWriter(test_db_path, read_only=True) as writer:
            sample_citation_data.source_id = 1
            with pytest.raises(RuntimeError, match="read-only"):
                writer.create_citation(sample_citation_data)

    def test_link_citation_to_person(self, test_db_path, sample_source_data, sample_citation_data):
        """Test linking a citation to a person."""
        with DraftDatabaseWriter(test_db_path, read_only=False) as writer:
            # Create source and citation
            sample_source_data.name = f"Link Test Source {Path(test_db_path).stem}"
            source_id, _ = writer.create_or_find_source(sample_source_data)
            sample_citation_data.source_id = source_id
            citation_id = writer.create_citation(sample_citation_data)

            # Link to person 1
            link_id = writer.link_citation_to_person(citation_id, person_id=1)

            assert link_id > 0

            # Verify link was created
            cursor = writer.conn.cursor()
            cursor.execute("""
                SELECT CitationID, OwnerType, OwnerID
                FROM CitationLinkTable WHERE LinkID = ?
            """, (link_id,))

            result = cursor.fetchone()
            assert result is not None
            cit_id, owner_type, owner_id = result
            assert cit_id == citation_id
            assert owner_type == 0  # Person
            assert owner_id == 1

    def test_link_citation_read_only_fails(self, test_db_path):
        """Test that linking citation in read-only mode fails."""
        with DraftDatabaseWriter(test_db_path, read_only=True) as writer:
            with pytest.raises(RuntimeError, match="read-only"):
                writer.link_citation_to_person(1, 1)

    def test_check_duplicate_citation(self, test_db_path, sample_source_data, sample_citation_data):
        """Test duplicate citation detection."""
        with DraftDatabaseWriter(test_db_path, read_only=False) as writer:
            # Create source
            sample_source_data.name = f"Dup Citation Test {Path(test_db_path).stem}"
            source_id, _ = writer.create_or_find_source(sample_source_data)

            # Initially no duplicate
            dup_id = writer.check_duplicate_citation(person_id=1, source_id=source_id)
            assert dup_id is None

            # Create and link citation
            sample_citation_data.source_id = source_id
            citation_id = writer.create_citation(sample_citation_data)
            writer.link_citation_to_person(citation_id, person_id=1)

            # Now should find duplicate
            dup_id = writer.check_duplicate_citation(person_id=1, source_id=source_id)
            assert dup_id == citation_id

    def test_get_person_citations_count(self, test_db_path):
        """Test getting citation count for a person."""
        with DraftDatabaseWriter(test_db_path, read_only=True) as writer:
            count = writer.get_person_citations_count(1)
            assert count >= 0


class TestCompleteWorkflow:
    """Test the complete citation creation workflow."""

    def test_create_citation_for_person(self, test_db_path, sample_source_data, sample_citation_data):
        """Test complete workflow of creating citation for person."""
        with DraftDatabaseWriter(test_db_path, read_only=False) as writer:
            # Create unique source name
            sample_source_data.name = f"Workflow Test {Path(test_db_path).stem}"

            # Execute complete workflow
            source_id, citation_id, link_id, source_created = writer.create_citation_for_person(
                person_id=1,
                source_data=sample_source_data,
                citation_data=sample_citation_data
            )

            assert source_id > 0
            assert citation_id > 0
            assert link_id > 0
            assert source_created is True

            # Verify everything was created correctly
            cursor = writer.conn.cursor()

            # Check source
            cursor.execute("SELECT Name FROM SourceTable WHERE SourceID = ?", (source_id,))
            assert cursor.fetchone() is not None

            # Check citation
            cursor.execute("SELECT SourceID FROM CitationTable WHERE CitationID = ?", (citation_id,))
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == source_id

            # Check link
            cursor.execute("""
                SELECT OwnerID FROM CitationLinkTable
                WHERE LinkID = ? AND OwnerType = 0
            """, (link_id,))
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == 1  # person_id

    def test_create_citation_for_person_reuses_source(self, test_db_path, sample_source_data, sample_citation_data):
        """Test that workflow reuses existing source."""
        with DraftDatabaseWriter(test_db_path, read_only=False) as writer:
            sample_source_data.name = f"Reuse Test {Path(test_db_path).stem}"

            # First citation
            source_id1, _, _, source_created1 = writer.create_citation_for_person(
                person_id=1,
                source_data=sample_source_data,
                citation_data=sample_citation_data
            )
            assert source_created1 is True

            # Second citation for different person, same source
            source_id2, _, _, source_created2 = writer.create_citation_for_person(
                person_id=2,
                source_data=sample_source_data,
                citation_data=sample_citation_data
            )
            assert source_created2 is False
            assert source_id2 == source_id1

    def test_create_citation_for_person_skips_duplicate(self, test_db_path, sample_source_data, sample_citation_data):
        """Test that workflow skips duplicate citations."""
        with DraftDatabaseWriter(test_db_path, read_only=False) as writer:
            sample_source_data.name = f"Skip Dup Test {Path(test_db_path).stem}"

            # First citation
            _, citation_id1, link_id1, _ = writer.create_citation_for_person(
                person_id=1,
                source_data=sample_source_data,
                citation_data=sample_citation_data
            )
            assert link_id1 > 0

            # Try to create same citation again
            _, citation_id2, link_id2, _ = writer.create_citation_for_person(
                person_id=1,
                source_data=sample_source_data,
                citation_data=sample_citation_data
            )
            assert citation_id2 == citation_id1
            assert link_id2 == 0  # No link created (duplicate)

    def test_create_citation_for_invalid_person_fails(self, test_db_path, sample_source_data, sample_citation_data):
        """Test that creating citation for non-existent person fails."""
        with DraftDatabaseWriter(test_db_path, read_only=False) as writer:
            with pytest.raises(ValueError, match="not found"):
                writer.create_citation_for_person(
                    person_id=999999,
                    source_data=sample_source_data,
                    citation_data=sample_citation_data
                )

    def test_create_citation_read_only_fails(self, test_db_path, sample_source_data, sample_citation_data):
        """Test that complete workflow fails in read-only mode."""
        with DraftDatabaseWriter(test_db_path, read_only=True) as writer:
            with pytest.raises(RuntimeError, match="read-only"):
                writer.create_citation_for_person(
                    person_id=1,
                    source_data=sample_source_data,
                    citation_data=sample_citation_data
                )


class TestTransactionBehavior:
    """Test transaction handling and rollback."""

    def test_commit_on_success(self, test_db_path, sample_source_data):
        """Test that changes are committed on successful exit."""
        sample_source_data.name = f"Commit Test {Path(test_db_path).stem}"

        # Create source in transaction
        with DraftDatabaseWriter(test_db_path, read_only=False) as writer:
            source_id, _ = writer.create_or_find_source(sample_source_data)

        # Verify source persists after closing
        with DraftDatabaseWriter(test_db_path, read_only=True) as writer:
            dup_id = writer.check_duplicate_source(sample_source_data)
            assert dup_id == source_id

    def test_rollback_on_exception(self, test_db_path, sample_source_data):
        """Test that changes are rolled back on exception."""
        sample_source_data.name = f"Rollback Test {Path(test_db_path).stem}"

        # Attempt to create source but raise exception
        try:
            with DraftDatabaseWriter(test_db_path, read_only=False) as writer:
                writer.create_or_find_source(sample_source_data)
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Verify source was not persisted
        with DraftDatabaseWriter(test_db_path, read_only=True) as writer:
            dup_id = writer.check_duplicate_source(sample_source_data)
            assert dup_id is None
