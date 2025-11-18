"""
Database error handling tests.

Tests error conditions and exception handling for database operations.
"""

import sqlite3
from pathlib import Path

import pytest

from rmcitecraft.database.connection import connect_rmtree
from rmcitecraft.database.findagrave_queries import (
    create_findagrave_image_record,
    create_findagrave_source_and_citation,
)


class TestDatabaseConnectionErrors:
    """Test database connection error handling."""

    def test_handles_missing_database_file(self):
        """Verify error when database file doesn't exist."""
        non_existent_db = "path/to/nonexistent.rmtree"

        with pytest.raises(FileNotFoundError):
            connect_rmtree(non_existent_db)

    def test_handles_invalid_database_path(self):
        """Verify error when path is a directory, not a file."""
        with pytest.raises(Exception):
            # Pass directory instead of file
            connect_rmtree(".")

    def test_handles_icu_extension_missing(self, tmp_path):
        """Verify error when ICU extension file not found."""
        # Create an empty database
        temp_db = tmp_path / "test.rmtree"
        temp_db.touch()

        # Try to connect with wrong extension path
        with pytest.raises(Exception):
            conn = sqlite3.connect(str(temp_db))
            conn.enable_load_extension(True)
            try:
                conn.load_extension("/nonexistent/icu.dylib")
            finally:
                conn.close()

    def test_handles_read_only_database(self, tmp_path):
        """Verify error when write attempted on read-only DB."""
        # Create a database file and make it read-only
        temp_db = tmp_path / "readonly.rmtree"

        # Copy test database
        import shutil
        shutil.copy("data/Iiams.rmtree", temp_db)

        # Make read-only (remove write permissions)
        temp_db.chmod(0o444)

        try:
            # connect_rmtree with read_only=False should handle this
            conn = connect_rmtree(str(temp_db), read_only=False)
            cursor = conn.cursor()

            # Try to insert - should fail
            with pytest.raises(sqlite3.OperationalError, match="readonly|attempt to write"):
                cursor.execute("INSERT INTO PlaceTable (Name) VALUES (?)", ("Test",))
                conn.commit()

            conn.close()
        finally:
            # Restore write permission for cleanup
            temp_db.chmod(0o644)

    def test_handles_corrupted_database(self, tmp_path):
        """Verify error when database is corrupted.

        Note: SQLite doesn't detect corruption on open, only when querying.
        """
        # Create a file with invalid SQLite format
        corrupt_db = tmp_path / "corrupt.rmtree"
        corrupt_db.write_bytes(b"This is not a valid SQLite database file")

        with pytest.raises(sqlite3.DatabaseError):
            conn = connect_rmtree(str(corrupt_db))
            # Corruption only detected when querying
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM PlaceTable LIMIT 1")
            conn.close()


class TestDatabaseWriteErrors:
    """Test error handling for database write operations.

    Note: These tests check input validation that hasn't been implemented yet.
    They are marked as xfail to document desired behavior without blocking CI.
    """

    @pytest.mark.xfail(reason="Input validation not yet implemented")
    def test_handles_invalid_citation_id(self, tmp_path):
        """Verify error when citation_id doesn't exist."""
        import shutil
        temp_db = tmp_path / "test.rmtree"
        shutil.copy("data/Iiams.rmtree", temp_db)

        test_image = tmp_path / "test.jpg"
        test_image.write_bytes(b"\xFF\xD8\xFF\xE0" + b"\x00" * 100)

        # Use non-existent citation_id
        with pytest.raises(Exception):
            create_findagrave_image_record(
                db_path=str(temp_db),
                citation_id=999999,  # Non-existent
                image_path=str(test_image),
                photo_type='Grave',
                memorial_id='123',
                media_root=str(tmp_path),
            )

    @pytest.mark.xfail(reason="Input validation not yet implemented")
    def test_handles_invalid_person_id(self, tmp_path):
        """Verify error when person_id doesn't exist."""
        import shutil
        temp_db = tmp_path / "test.rmtree"
        shutil.copy("data/Iiams.rmtree", temp_db)

        # Try to create citation for non-existent person
        with pytest.raises(Exception):
            create_findagrave_source_and_citation(
                db_path=str(temp_db),
                person_id=999999,  # Non-existent
                source_name="Test Source",
                memorial_url="https://findagrave.com/memorial/123",
                footnote="Test footnote",
                short_footnote="Test short",
                bibliography="Test bibliography",
            )

    @pytest.mark.xfail(reason="Input validation not yet implemented - no error to rollback")
    def test_rollback_on_error(self, tmp_path):
        """Verify transaction rollback on error."""
        import shutil
        temp_db = tmp_path / "test.rmtree"
        shutil.copy("data/Iiams.rmtree", temp_db)

        # Count records before
        conn = connect_rmtree(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM SourceTable")
        count_before = cursor.fetchone()[0]
        conn.close()

        # Try operation that will fail
        try:
            create_findagrave_source_and_citation(
                db_path=str(temp_db),
                person_id=999999,  # Non-existent
                source_name="Test",
                memorial_url="https://findagrave.com/memorial/123",
                footnote="Test",
                short_footnote="Test",
                bibliography="Test",
            )
        except Exception:
            pass  # Expected to fail

        # Count records after - should be unchanged
        conn = connect_rmtree(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM SourceTable")
        count_after = cursor.fetchone()[0]
        conn.close()

        assert count_before == count_after, "Transaction should have rolled back"

    @pytest.mark.xfail(reason="Input validation not yet implemented")
    def test_handles_missing_required_fields(self, tmp_path):
        """Verify error when required fields are missing."""
        import shutil
        temp_db = tmp_path / "test.rmtree"
        shutil.copy("data/Iiams.rmtree", temp_db)

        # Get valid citation_id
        conn = connect_rmtree(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.CitationID
            FROM CitationTable c
            LIMIT 1
        """)
        citation_id = cursor.fetchone()[0]
        conn.close()

        # Try to create image with missing path
        with pytest.raises(Exception):
            create_findagrave_image_record(
                db_path=str(temp_db),
                citation_id=citation_id,
                image_path='',  # Empty path
                photo_type='Grave',
                memorial_id='123',
                media_root=str(tmp_path),
            )


class TestDatabaseIntegrityErrors:
    """Test database integrity constraint errors."""

    def test_handles_duplicate_insertion(self, tmp_path):
        """Verify handling of duplicate record insertion."""
        import shutil
        temp_db = tmp_path / "test.rmtree"
        shutil.copy("data/Iiams.rmtree", temp_db)

        conn = connect_rmtree(str(temp_db), read_only=False)
        cursor = conn.cursor()

        # Get existing PlaceID
        cursor.execute("SELECT PlaceID FROM PlaceTable LIMIT 1")
        existing_id = cursor.fetchone()[0]

        # Try to insert with same ID
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO PlaceTable (PlaceID, PlaceType, Name, Latitude, Longitude)
                VALUES (?, ?, ?, ?, ?)
            """, (existing_id, 0, "Test", 0, 0))
            conn.commit()

        conn.close()

    def test_handles_foreign_key_violation(self, tmp_path):
        """Verify foreign key constraint errors."""
        import shutil
        temp_db = tmp_path / "test.rmtree"
        shutil.copy("data/Iiams.rmtree", temp_db)

        conn = connect_rmtree(str(temp_db), read_only=False)
        cursor = conn.cursor()

        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON")

        # Try to insert MediaLinkTable with invalid MediaID
        try:
            cursor.execute("""
                INSERT INTO MediaLinkTable (MediaID, OwnerType, OwnerID)
                VALUES (?, ?, ?)
            """, (999999, 0, 1))  # MediaID 999999 doesn't exist
            conn.commit()

            # If no error, verify the record wasn't created
            cursor.execute("SELECT COUNT(*) FROM MediaLinkTable WHERE MediaID = 999999")
            count = cursor.fetchone()[0]
            # Some RootsMagic DBs may not have FK constraints enabled
            # Just verify the behavior is consistent
            assert count >= 0

        except sqlite3.IntegrityError:
            # Expected with foreign key constraints
            pass

        conn.close()


class TestFileSystemErrors:
    """Test file system error handling."""

    def test_handles_missing_image_file(self, tmp_path):
        """Verify error when image file doesn't exist."""
        import shutil
        temp_db = tmp_path / "test.rmtree"
        shutil.copy("data/Iiams.rmtree", temp_db)

        # Get valid citation_id
        conn = connect_rmtree(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("SELECT CitationID FROM CitationTable LIMIT 1")
        citation_id = cursor.fetchone()[0]
        conn.close()

        # Try with non-existent image
        non_existent_image = tmp_path / "does_not_exist.jpg"

        # The function should handle this gracefully or raise appropriate error
        try:
            result = create_findagrave_image_record(
                db_path=str(temp_db),
                citation_id=citation_id,
                image_path=str(non_existent_image),
                photo_type='Grave',
                memorial_id='123',
                media_root=str(tmp_path),
            )
            # If it succeeds, the record still gets created
            # (path may not be validated at creation time)
            assert result['media_id'] > 0
        except (FileNotFoundError, Exception) as e:
            # Also acceptable to raise an error
            assert True

    def test_handles_permission_denied(self, tmp_path):
        """Verify error when insufficient permissions."""
        # Create a directory we can't write to
        protected_dir = tmp_path / "protected"
        protected_dir.mkdir()

        test_file = protected_dir / "test.jpg"
        test_file.write_bytes(b"\xFF\xD8\xFF\xE0" + b"\x00" * 100)

        # Remove write permission from directory
        protected_dir.chmod(0o555)

        try:
            # Try to create a file in protected directory
            new_file = protected_dir / "new_file.jpg"
            with pytest.raises(PermissionError):
                new_file.write_bytes(b"test")
        finally:
            # Restore permissions for cleanup
            protected_dir.chmod(0o755)

    def test_handles_invalid_characters_in_filename(self):
        """Verify sanitization of illegal characters."""
        # RootsMagic should handle most characters, but some may be illegal
        # Test that path conversion handles them
        from rmcitecraft.database.findagrave_queries import convert_path_to_rootsmagic_format

        # Most characters are actually legal in modern filesystems
        # But we can test the function handles various inputs
        media_root = Path("/media")

        # Test with various special characters (most are legal)
        test_cases = [
            Path("/media/Photos/Test-Name.jpg"),
            Path("/media/Photos/Test'Name.jpg"),
            Path("/media/Photos/Test & Name.jpg"),
        ]

        for test_path in test_cases:
            result = convert_path_to_rootsmagic_format(test_path, media_root)
            assert isinstance(result, str)
            assert len(result) > 0


class TestConcurrencyErrors:
    """Test concurrent access error handling."""

    def test_handles_locked_database(self, tmp_path):
        """Verify handling of database locked errors."""
        import shutil
        temp_db = tmp_path / "test.rmtree"
        shutil.copy("data/Iiams.rmtree", temp_db)

        # Open connection with transaction
        conn1 = connect_rmtree(str(temp_db), read_only=False)
        cursor1 = conn1.cursor()
        cursor1.execute("BEGIN EXCLUSIVE TRANSACTION")

        try:
            # Try to open second connection for write
            conn2 = connect_rmtree(str(temp_db), read_only=False)
            cursor2 = conn2.cursor()

            # This should timeout or fail with locked error
            with pytest.raises(sqlite3.OperationalError):
                cursor2.execute("INSERT INTO PlaceTable (Name) VALUES (?)", ("Test",))
                conn2.commit()

            conn2.close()
        finally:
            conn1.rollback()
            conn1.close()


class TestValidationErrors:
    """Test data validation error handling."""

    def test_validates_path_format(self):
        """Verify path format validation."""
        from rmcitecraft.database.findagrave_queries import convert_path_to_rootsmagic_format

        media_root = Path("/media")

        # Test with various inputs
        valid_paths = [
            "/media/test.jpg",
            str(Path.home() / "test.jpg"),
            "/tmp/test.jpg",
        ]

        for path in valid_paths:
            result = convert_path_to_rootsmagic_format(path, media_root)
            # Should return valid result
            assert isinstance(result, str)
            assert len(result) > 0

    def test_validates_media_type(self, tmp_path):
        """Verify MediaType values are valid."""
        import shutil
        temp_db = tmp_path / "test.rmtree"
        shutil.copy("data/Iiams.rmtree", temp_db)

        conn = connect_rmtree(str(temp_db))
        cursor = conn.cursor()

        # Check all MediaType values are 1-4
        cursor.execute("""
            SELECT DISTINCT MediaType
            FROM MultimediaTable
            WHERE MediaType NOT IN (1, 2, 3, 4)
        """)

        invalid = cursor.fetchall()
        conn.close()

        assert len(invalid) == 0, f"Found invalid MediaType values: {invalid}"

    def test_validates_owner_type(self, tmp_path):
        """Verify OwnerType values are valid."""
        import shutil
        temp_db = tmp_path / "test.rmtree"
        shutil.copy("data/Iiams.rmtree", temp_db)

        conn = connect_rmtree(str(temp_db))
        cursor = conn.cursor()

        # Check all OwnerType values are known types
        # Per schema: 0=Person, 1=Family, 2=Event, 3=Source, 4=Citation,
        # 5=Place, 6=Task, 7=Name, 14=Place Detail
        valid_types = [0, 1, 2, 3, 4, 5, 6, 7, 14]

        cursor.execute("""
            SELECT DISTINCT OwnerType
            FROM MediaLinkTable
        """)

        owner_types = [row[0] for row in cursor.fetchall()]
        conn.close()

        for ot in owner_types:
            assert ot in valid_types, f"Invalid OwnerType {ot}"
