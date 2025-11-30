"""Unit tests for primary photo assignment feature."""

import sqlite3
import pytest
from pathlib import Path

from rmcitecraft.database.findagrave_queries import create_findagrave_image_record


class TestPrimaryPhotoAssignment:
    """Test primary photo assignment for Person photos."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a test database with required schema."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Create required tables
        cursor.execute("""
            CREATE TABLE MultimediaTable (
                MediaID INTEGER PRIMARY KEY AUTOINCREMENT,
                MediaType INTEGER,
                MediaPath TEXT,
                MediaFile TEXT,
                URL TEXT,
                Thumbnail BLOB,
                Caption TEXT,
                RefNumber TEXT,
                Date TEXT,
                SortDate BIGINT,
                Description TEXT,
                UTCModDate FLOAT
            )
        """)

        cursor.execute("""
            CREATE TABLE MediaLinkTable (
                LinkID INTEGER PRIMARY KEY,
                MediaID INTEGER,
                OwnerType INTEGER,
                OwnerID INTEGER,
                IsPrimary INTEGER,
                UTCModDate FLOAT
            )
        """)

        cursor.execute("""
            CREATE TABLE CitationTable (
                CitationID INTEGER PRIMARY KEY,
                SourceID INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE SourceTable (
                SourceID INTEGER PRIMARY KEY,
                Name TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE CitationLinkTable (
                LinkID INTEGER PRIMARY KEY,
                CitationID INTEGER,
                OwnerType INTEGER,
                OwnerID INTEGER,
                SortOrder INTEGER,
                Quality TEXT,
                IsPrivate INTEGER,
                Flags INTEGER,
                UTCModDate FLOAT
            )
        """)

        # Insert test data
        cursor.execute("INSERT INTO SourceTable (SourceID, Name) VALUES (1, 'Test Source')")
        cursor.execute("INSERT INTO CitationTable (CitationID, SourceID) VALUES (100, 1)")

        conn.commit()
        conn.close()

        return str(db_path)

    @pytest.fixture
    def test_image(self, tmp_path):
        """Create a test image file."""
        media_root = tmp_path / "media"
        media_root.mkdir(exist_ok=True)

        image_path = media_root / "test_person.jpg"
        image_path.write_bytes(b"fake image data")

        return str(image_path), str(media_root)

    def test_first_person_photo_is_primary(self, test_db, test_image):
        """Test that the first Person photo is marked as primary."""
        image_path, media_root = test_image

        # Create first Person photo
        result = create_findagrave_image_record(
            db_path=test_db,
            citation_id=100,
            person_id=1,
            image_path=image_path,
            photo_type='Person',
            memorial_id='12345',
            photo_id='67890',
            contributor='Test Contributor',
            person_name='John Doe',
            media_root=media_root,
        )

        # Verify photo was created
        assert result['media_id'] is not None
        assert result['media_link_id'] is not None

        # Verify IsPrimary=1 for Person link
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT IsPrimary FROM MediaLinkTable
            WHERE MediaID = ? AND OwnerType = 0 AND OwnerID = 1
        """, (result['media_id'],))

        is_primary = cursor.fetchone()[0]
        conn.close()

        assert is_primary == 1, "First Person photo should have IsPrimary=1"

    def test_second_person_photo_not_primary(self, test_db, test_image, tmp_path):
        """Test that the second Person photo is not marked as primary."""
        image_path, media_root = test_image

        # Create first Person photo
        result1 = create_findagrave_image_record(
            db_path=test_db,
            citation_id=100,
            person_id=1,
            image_path=image_path,
            photo_type='Person',
            memorial_id='12345',
            photo_id='67890',
            contributor='Test Contributor',
            person_name='John Doe',
            media_root=media_root,
        )

        # Create second Person photo (different file)
        image_path_2 = Path(media_root) / "test_person_2.jpg"
        image_path_2.write_bytes(b"fake image data 2")

        result2 = create_findagrave_image_record(
            db_path=test_db,
            citation_id=100,
            person_id=1,
            image_path=str(image_path_2),
            photo_type='Person',
            memorial_id='12345',
            photo_id='67891',
            contributor='Test Contributor',
            person_name='John Doe',
            media_root=media_root,
        )

        # Verify second photo has IsPrimary=0
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT IsPrimary FROM MediaLinkTable
            WHERE MediaID = ? AND OwnerType = 0 AND OwnerID = 1
        """, (result2['media_id'],))

        is_primary = cursor.fetchone()[0]
        conn.close()

        assert is_primary == 0, "Second Person photo should have IsPrimary=0"

    def test_family_photo_not_primary(self, test_db, test_image):
        """Test that Family photos are never marked as primary."""
        image_path, media_root = test_image

        # Create Family photo (even as first photo)
        result = create_findagrave_image_record(
            db_path=test_db,
            citation_id=100,
            person_id=1,
            image_path=image_path,
            photo_type='Family',
            memorial_id='12345',
            photo_id='67890',
            contributor='Test Contributor',
            person_name='John Doe',
            media_root=media_root,
        )

        # Verify IsPrimary=0 for Family link
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT IsPrimary FROM MediaLinkTable
            WHERE MediaID = ? AND OwnerType = 0 AND OwnerID = 1
        """, (result['media_id'],))

        is_primary = cursor.fetchone()[0]
        conn.close()

        assert is_primary == 0, "Family photo should never have IsPrimary=1"

    def test_grave_photo_not_primary(self, test_db, test_image):
        """Test that Grave photos are never marked as primary for person links."""
        image_path, media_root = test_image

        # Note: Grave photos don't link to person (OwnerType=0), they link to burial event (OwnerType=2)
        # This test verifies no person link is created for Grave photos
        result = create_findagrave_image_record(
            db_path=test_db,
            citation_id=100,
            person_id=1,
            image_path=image_path,
            photo_type='Grave',
            memorial_id='12345',
            photo_id='67890',
            contributor='Test Contributor',
            person_name='John Doe',
            cemetery_name='Forest Lawn',
            cemetery_city='Detroit',
            cemetery_county='Wayne',
            cemetery_state='Michigan',
            media_root=media_root,
        )

        # Verify NO person link exists for Grave photo
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM MediaLinkTable
            WHERE MediaID = ? AND OwnerType = 0 AND OwnerID = 1
        """, (result['media_id'],))

        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0, "Grave photo should not have person link (OwnerType=0)"

    def test_person_photo_after_existing_primary(self, test_db, tmp_path):
        """Test that new Person photo respects existing primary photo."""
        media_root = tmp_path / "media"
        media_root.mkdir(exist_ok=True)

        # Manually create an existing primary photo link (simulating pre-existing data)
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Insert existing media record
        cursor.execute("""
            INSERT INTO MultimediaTable (MediaID, MediaType, MediaPath, MediaFile, Caption, UTCModDate)
            VALUES (999, 1, '?', 'existing_photo.jpg', 'Existing Photo', 0.0)
        """)

        # Insert existing primary link
        cursor.execute("""
            INSERT INTO MediaLinkTable (LinkID, MediaID, OwnerType, OwnerID, IsPrimary, UTCModDate)
            VALUES (1, 999, 0, 1, 1, 0.0)
        """)

        conn.commit()
        conn.close()

        # Now create a new Person photo
        image_path = media_root / "new_person.jpg"
        image_path.write_bytes(b"fake image data")

        result = create_findagrave_image_record(
            db_path=test_db,
            citation_id=100,
            person_id=1,
            image_path=str(image_path),
            photo_type='Person',
            memorial_id='12345',
            photo_id='67890',
            contributor='Test Contributor',
            person_name='John Doe',
            media_root=str(media_root),
        )

        # Verify new photo has IsPrimary=0 (because primary already exists)
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT IsPrimary FROM MediaLinkTable
            WHERE MediaID = ? AND OwnerType = 0 AND OwnerID = 1
        """, (result['media_id'],))

        is_primary = cursor.fetchone()[0]
        conn.close()

        assert is_primary == 0, "New Person photo should not be primary when one already exists"
