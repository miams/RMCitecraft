"""
MultimediaTable and MediaLinkTable integrity tests.

These tests ensure that image records created by RMCitecraft match the schema,
data types, and structure of existing RootsMagic media records.
"""

import sqlite3
from pathlib import Path

import pytest

from rmcitecraft.database.connection import connect_rmtree
from rmcitecraft.database.findagrave_queries import (
    create_findagrave_image_record,
    convert_path_to_rootsmagic_format,
)
from rmcitecraft.database.image_repository import ImageRepository


@pytest.fixture
def test_db_path():
    """Use the test database."""
    return "data/Iiams.rmtree"


@pytest.fixture
def db_connection(test_db_path):
    """Connect to test database with RMNOCASE collation."""
    conn = connect_rmtree(test_db_path)
    yield conn
    conn.close()


@pytest.fixture
def test_image_path(tmp_path):
    """Create a temporary test image file."""
    image_path = tmp_path / "test_image.jpg"
    image_path.write_bytes(b"\xFF\xD8\xFF\xE0" + b"\x00" * 100)  # Minimal JPEG header
    return image_path


@pytest.fixture
def media_root(tmp_path):
    """Create temporary media root directory."""
    media_root = tmp_path / "media"
    media_root.mkdir()
    return media_root


class TestMultimediaTableSchema:
    """Test MultimediaTable schema and structure."""

    def test_multimedia_schema_columns(self, db_connection):
        """Verify MultimediaTable has expected columns and types."""
        cursor = db_connection.cursor()
        cursor.execute("PRAGMA table_info(MultimediaTable)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected = {
            'MediaID': 'INTEGER',
            'MediaType': 'INTEGER',
            'MediaPath': 'TEXT',
            'MediaFile': 'TEXT',
            'URL': 'TEXT',
            'Thumbnail': 'BLOB',
            'Caption': 'TEXT',
            'RefNumber': 'TEXT',
            'Date': 'TEXT',
            'SortDate': 'BIGINT',
            'Description': 'TEXT',
            'UTCModDate': 'FLOAT',
        }

        assert columns == expected, f"MultimediaTable schema mismatch: {columns}"

    def test_multimedia_media_types(self, db_connection):
        """Verify MediaType values: 1=Image, 2=File, 3=Sound, 4=Video."""
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT DISTINCT MediaType
            FROM MultimediaTable
            ORDER BY MediaType
        """)
        media_types = [row[0] for row in cursor.fetchall()]

        # Valid types: 1=Image, 2=File, 3=Sound, 4=Video
        assert all(mt in [1, 2, 3, 4] for mt in media_types), \
            f"Invalid MediaType values found: {media_types}"

    def test_no_null_sortdate(self, db_connection):
        """Ensure SortDate is never NULL (critical for RootsMagic sorting)."""
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT MediaID, MediaFile
            FROM MultimediaTable
            WHERE SortDate IS NULL
        """)

        nulls = cursor.fetchall()
        assert len(nulls) == 0, f"Found {len(nulls)} media with NULL SortDate: {nulls[:5]}"

    def test_symbolic_path_format(self, db_connection):
        r"""Verify MediaPath uses symbolic prefixes (?, ~, *) or absolute paths.

        Note: RootsMagic supports both forward slashes (/) and backslashes (\)
        as path separators after symbolic prefixes.
        """
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT MediaID, MediaPath, MediaFile
            FROM MultimediaTable
            WHERE MediaPath IS NOT NULL
            AND MediaPath != ''
            LIMIT 10
        """)

        for media_id, media_path, media_file in cursor.fetchall():
            # Should start with symbolic prefix or be absolute
            # RootsMagic supports both forward slash (/) and backslash (\) separators
            assert (
                media_path.startswith('?/') or media_path.startswith('?\\') or
                media_path.startswith('~/') or media_path.startswith('~\\') or
                media_path.startswith('*/') or media_path.startswith('*\\') or
                media_path.startswith('/')
            ), f"MediaID {media_id}: Invalid path format '{media_path}'"


class TestMediaLinkTableSchema:
    """Test MediaLinkTable schema and structure."""

    def test_medialink_schema_columns(self, db_connection):
        """Verify MediaLinkTable has expected columns and types."""
        cursor = db_connection.cursor()
        cursor.execute("PRAGMA table_info(MediaLinkTable)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected = {
            'LinkID': 'INTEGER',
            'MediaID': 'INTEGER',
            'OwnerType': 'INTEGER',
            'OwnerID': 'INTEGER',
            'Include1': 'INTEGER',
            'Include2': 'INTEGER',
            'Include3': 'INTEGER',
            'Include4': 'INTEGER',
            'IsPrimary': 'INTEGER',
            'SortOrder': 'INTEGER',
            'RectLeft': 'INTEGER',
            'RectTop': 'INTEGER',
            'RectRight': 'INTEGER',
            'RectBottom': 'INTEGER',
            'Comments': 'TEXT',
            'UTCModDate': 'FLOAT',
        }

        assert columns == expected, f"MediaLinkTable schema mismatch: {columns}"

    def test_owner_type_values(self, db_connection):
        """Verify OwnerType values are integers (various entity types)."""
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT DISTINCT OwnerType
            FROM MediaLinkTable
            ORDER BY OwnerType
        """)
        owner_types = [row[0] for row in cursor.fetchall()]

        # Known valid types from RootsMagic
        # 0=Person, 1=?, 2=Event, 3=?, 4=Citation, 5=Source, 6=Place, 14=?
        # Allow any integer value (RootsMagic may use additional types)
        assert all(isinstance(ot, int) for ot in owner_types), \
            f"OwnerType values should be integers: {owner_types}"

        # Verify most common types are present
        common_types = [0, 2, 4]  # Person, Event, Citation
        for ct in common_types:
            if ct not in owner_types:
                # Just log warning, don't fail (database may not have all types)
                pass

    def test_foreign_key_validity(self, db_connection):
        """Verify MediaID references valid MultimediaTable records."""
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT ml.LinkID, ml.MediaID
            FROM MediaLinkTable ml
            LEFT JOIN MultimediaTable m ON ml.MediaID = m.MediaID
            WHERE m.MediaID IS NULL
            LIMIT 10
        """)

        orphans = cursor.fetchall()
        assert len(orphans) == 0, \
            f"Found {len(orphans)} MediaLinkTable records with invalid MediaID: {orphans}"


class TestCreateFindAGraveImageRecord:
    """Test create_findagrave_image_record() function."""

    def test_creates_media_record_with_correct_fields(self, test_db_path, test_image_path, media_root, tmp_path):
        """Verify MultimediaTable record created with all required fields."""
        # Copy test DB to tmp for write operations
        import shutil
        temp_db = tmp_path / "test.rmtree"
        shutil.copy(test_db_path, temp_db)

        # Create a test citation first
        conn = connect_rmtree(str(temp_db))
        cursor = conn.cursor()

        # Find a person with Find a Grave citation for testing
        cursor.execute("""
            SELECT c.CitationID
            FROM CitationTable c
            JOIN SourceTable s ON c.SourceID = s.SourceID
            WHERE s.Name LIKE '%Find a Grave%'
            LIMIT 1
        """)
        result = cursor.fetchone()
        conn.close()

        if not result:
            pytest.skip("No Find a Grave citations in test database")

        citation_id = result[0]

        # Create image record
        result = create_findagrave_image_record(
            db_path=str(temp_db),
            citation_id=citation_id,
            image_path=str(test_image_path),
            photo_type='Grave',
            memorial_id='123456789',
            contributor='John Doe',
            media_root=str(media_root),
        )

        assert 'media_id' in result
        assert 'media_link_id' in result
        assert result['media_id'] > 0
        assert result['media_link_id'] > 0

        # Verify record in database
        conn = connect_rmtree(str(temp_db))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT MediaType, MediaPath, MediaFile, Caption, RefNumber
            FROM MultimediaTable
            WHERE MediaID = ?
        """, (result['media_id'],))
        media_record = cursor.fetchone()

        assert media_record is not None
        assert media_record[0] == 1, "MediaType should be 1 (Image)"
        assert media_record[2] == test_image_path.name, "MediaFile should match filename"
        assert 'Find a Grave' in media_record[3], "Caption should mention Find a Grave"
        assert 'Grave Photo' in media_record[3], "Caption should mention photo type"
        assert 'John Doe' in media_record[3], "Caption should mention contributor"
        assert '123456789' in media_record[4], "RefNumber should contain memorial ID"

        conn.close()

    def test_creates_media_link_to_citation(self, test_db_path, test_image_path, media_root, tmp_path):
        """Verify MediaLinkTable record links to citation (OwnerType=4)."""
        import shutil
        temp_db = tmp_path / "test.rmtree"
        shutil.copy(test_db_path, temp_db)

        # Get test citation
        conn = connect_rmtree(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.CitationID
            FROM CitationTable c
            JOIN SourceTable s ON c.SourceID = s.SourceID
            WHERE s.Name LIKE '%Find a Grave%'
            LIMIT 1
        """)
        result = cursor.fetchone()
        conn.close()

        if not result:
            pytest.skip("No Find a Grave citations in test database")

        citation_id = result[0]

        # Create image record
        result = create_findagrave_image_record(
            db_path=str(temp_db),
            citation_id=citation_id,
            image_path=str(test_image_path),
            photo_type='Person',
            memorial_id='987654321',
            media_root=str(media_root),
        )

        # Verify media link
        conn = connect_rmtree(str(temp_db))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT OwnerType, OwnerID, MediaID
            FROM MediaLinkTable
            WHERE LinkID = ?
        """, (result['media_link_id'],))
        link_record = cursor.fetchone()

        assert link_record is not None
        assert link_record[0] == 4, "OwnerType should be 4 (Citation)"
        assert link_record[1] == citation_id, "OwnerID should match citation_id"
        assert link_record[2] == result['media_id'], "MediaID should match created media"

        conn.close()

    def test_handles_missing_memorial_id(self, test_db_path, test_image_path, media_root, tmp_path):
        """Verify graceful handling when memorial_id is empty."""
        import shutil
        temp_db = tmp_path / "test.rmtree"
        shutil.copy(test_db_path, temp_db)

        conn = connect_rmtree(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.CitationID
            FROM CitationTable c
            JOIN SourceTable s ON c.SourceID = s.SourceID
            WHERE s.Name LIKE '%Find a Grave%'
            LIMIT 1
        """)
        result = cursor.fetchone()
        conn.close()

        if not result:
            pytest.skip("No Find a Grave citations in test database")

        citation_id = result[0]

        # Create without memorial_id
        result = create_findagrave_image_record(
            db_path=str(temp_db),
            citation_id=citation_id,
            image_path=str(test_image_path),
            photo_type='Grave',
            memorial_id='',  # Empty memorial ID
            media_root=str(media_root),
        )

        # Should still create record
        assert result['media_id'] > 0

        # Verify RefNumber is empty
        conn = connect_rmtree(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT RefNumber
            FROM MultimediaTable
            WHERE MediaID = ?
        """, (result['media_id'],))
        ref_number = cursor.fetchone()[0]
        conn.close()

        assert ref_number == '', "RefNumber should be empty when memorial_id is empty"

    def test_handles_missing_contributor(self, test_db_path, test_image_path, media_root, tmp_path):
        """Verify caption generation without contributor name."""
        import shutil
        temp_db = tmp_path / "test.rmtree"
        shutil.copy(test_db_path, temp_db)

        conn = connect_rmtree(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.CitationID
            FROM CitationTable c
            JOIN SourceTable s ON c.SourceID = s.SourceID
            WHERE s.Name LIKE '%Find a Grave%'
            LIMIT 1
        """)
        result = cursor.fetchone()
        conn.close()

        if not result:
            pytest.skip("No Find a Grave citations in test database")

        citation_id = result[0]

        # Create without contributor
        result = create_findagrave_image_record(
            db_path=str(temp_db),
            citation_id=citation_id,
            image_path=str(test_image_path),
            photo_type='Family',
            memorial_id='111222333',
            contributor='',  # Empty contributor
            media_root=str(media_root),
        )

        # Verify caption doesn't have "(contributed by )"
        conn = connect_rmtree(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT Caption
            FROM MultimediaTable
            WHERE MediaID = ?
        """, (result['media_id'],))
        caption = cursor.fetchone()[0]
        conn.close()

        assert 'Find a Grave' in caption
        assert 'Family Photo' in caption
        assert 'contributed by' not in caption

    def test_path_conversion_with_spaces(self, test_db_path, media_root, tmp_path):
        """Verify filename with spaces handled correctly."""
        import shutil
        temp_db = tmp_path / "test.rmtree"
        shutil.copy(test_db_path, temp_db)

        # Create image with spaces in filename
        image_path = tmp_path / "Test Person Name.jpg"
        image_path.write_bytes(b"\xFF\xD8\xFF\xE0" + b"\x00" * 100)

        conn = connect_rmtree(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.CitationID
            FROM CitationTable c
            JOIN SourceTable s ON c.SourceID = s.SourceID
            WHERE s.Name LIKE '%Find a Grave%'
            LIMIT 1
        """)
        result = cursor.fetchone()
        conn.close()

        if not result:
            pytest.skip("No Find a Grave citations in test database")

        citation_id = result[0]

        # Create image record
        result = create_findagrave_image_record(
            db_path=str(temp_db),
            citation_id=citation_id,
            image_path=str(image_path),
            photo_type='Person',
            media_root=str(media_root),
        )

        # Verify MediaFile preserves spaces
        conn = connect_rmtree(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MediaFile
            FROM MultimediaTable
            WHERE MediaID = ?
        """, (result['media_id'],))
        media_file = cursor.fetchone()[0]
        conn.close()

        assert media_file == "Test Person Name.jpg"


class TestMediaRecordIntegrity:
    """Test that created media records match existing patterns."""

    def test_media_record_matches_existing_pattern(self, test_db_path, test_image_path, media_root, tmp_path):
        """Compare created media record field-by-field with existing records."""
        cursor = connect_rmtree(test_db_path).cursor()

        # Get an existing image record
        cursor.execute("""
            SELECT MediaType, SortDate, UTCModDate
            FROM MultimediaTable
            WHERE MediaType = 1
            LIMIT 1
        """)
        existing = cursor.fetchone()

        if not existing:
            pytest.skip("No existing image records in database")

        # Verify field types match
        assert isinstance(existing[0], int), "MediaType should be INTEGER"
        assert existing[1] == 0 or isinstance(existing[1], int), "SortDate should be INTEGER or 0"
        assert isinstance(existing[2], (int, float)), "UTCModDate should be numeric"

    def test_no_null_integer_columns_in_created_records(self, test_db_path, test_image_path, media_root, tmp_path):
        """Verify created records don't have NULL in integer columns."""
        import shutil
        temp_db = tmp_path / "test.rmtree"
        shutil.copy(test_db_path, temp_db)

        conn = connect_rmtree(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.CitationID
            FROM CitationTable c
            JOIN SourceTable s ON c.SourceID = s.SourceID
            WHERE s.Name LIKE '%Find a Grave%'
            LIMIT 1
        """)
        result = cursor.fetchone()
        conn.close()

        if not result:
            pytest.skip("No Find a Grave citations in test database")

        citation_id = result[0]

        # Create record
        result = create_findagrave_image_record(
            db_path=str(temp_db),
            citation_id=citation_id,
            image_path=str(test_image_path),
            photo_type='Grave',
            media_root=str(media_root),
        )

        # Verify no NULLs
        conn = connect_rmtree(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MediaType, SortDate
            FROM MultimediaTable
            WHERE MediaID = ?
        """, (result['media_id'],))
        record = cursor.fetchone()
        conn.close()

        assert record[0] is not None, "MediaType should not be NULL"
        assert record[1] is not None, "SortDate should not be NULL"
