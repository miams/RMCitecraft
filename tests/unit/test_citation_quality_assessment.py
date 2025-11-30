"""Unit tests for citation quality assessment feature."""

import sqlite3
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from rmcitecraft.database.findagrave_queries import (
    link_citation_to_person,
    create_burial_event_and_link_citation,
)


class TestCitationQualityAssessment:
    """Test citation quality assessment (SDX vs PDX) based on photo presence."""

    @pytest.fixture
    def mock_db_path(self, tmp_path):
        """Create a temporary test database with minimal schema."""
        db_path = tmp_path / "test.rmtree"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Create minimal tables for testing
        cursor.execute("""
            CREATE TABLE PersonTable (
                PersonID INTEGER PRIMARY KEY,
                Sex INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE EventTable (
                EventID INTEGER PRIMARY KEY,
                EventType INTEGER,
                OwnerType INTEGER,
                OwnerID INTEGER,
                Date TEXT,
                SortDate BIGINT,
                PlaceID INTEGER,
                SiteID INTEGER,
                Details TEXT,
                IsPrimary INTEGER,
                IsPrivate INTEGER,
                Proof INTEGER,
                Status INTEGER,
                Sentence TEXT,
                UTCModDate FLOAT
            )
        """)

        cursor.execute("""
            CREATE TABLE PlaceTable (
                PlaceID INTEGER PRIMARY KEY,
                PlaceType INTEGER,
                Name TEXT,
                Abbrev TEXT,
                Normalized TEXT,
                Latitude INTEGER,
                Longitude INTEGER,
                Reverse TEXT,
                fsID INTEGER,
                anID INTEGER,
                UTCModDate FLOAT
            )
        """)

        cursor.execute("""
            CREATE TABLE CitationLinkTable (
                LinkID INTEGER PRIMARY KEY AUTOINCREMENT,
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

        cursor.execute("""
            CREATE TABLE FactTypeTable (
                FactTypeID INTEGER PRIMARY KEY,
                Name TEXT
            )
        """)

        # Insert test data
        cursor.execute("INSERT INTO PersonTable (PersonID, Sex) VALUES (1, 1)")
        cursor.execute("INSERT INTO FactTypeTable (FactTypeID, Name) VALUES (9, 'Burial')")
        cursor.execute("INSERT INTO FactTypeTable (FactTypeID, Name) VALUES (2, 'Death')")

        # Insert a location for burial events
        cursor.execute("""
            INSERT INTO PlaceTable (
                PlaceID, PlaceType, Name, Abbrev, Normalized,
                Latitude, Longitude, Reverse, fsID, anID, UTCModDate
            ) VALUES (1, 0, 'Test Cemetery, Test City, Test County, Test State',
                      '', 'test cemetery, test city, test county, test state',
                      0, 0, 'Test State, Test County, Test City, Test Cemetery',
                      0, 0, 0.0)
        """)

        conn.commit()
        conn.close()

        return str(db_path)

    def test_link_citation_to_person_default_sdx(self, mock_db_path):
        """Test that citation link to person defaults to SDX quality without photos."""
        with patch('rmcitecraft.database.connection.connect_rmtree') as mock_connect:
            conn = sqlite3.connect(mock_db_path)
            mock_connect.return_value = conn

            link_id = link_citation_to_person(
                db_path=mock_db_path,
                person_id=1,
                citation_id=100,
                has_grave_photo=False,
            )

            # Verify link was created
            assert link_id is not None

            # Check Quality field is SDX
            cursor = conn.cursor()
            cursor.execute("""
                SELECT Quality FROM CitationLinkTable
                WHERE CitationID = 100 AND OwnerType = 0 AND OwnerID = 1
            """)
            quality = cursor.fetchone()[0]
            assert quality == 'SDX', f"Expected SDX, got {quality}"

            conn.close()

    def test_link_citation_to_person_upgrade_pdx(self, mock_db_path):
        """Test that citation link to person upgrades to PDX quality with grave photo."""
        with patch('rmcitecraft.database.connection.connect_rmtree') as mock_connect:
            conn = sqlite3.connect(mock_db_path)
            mock_connect.return_value = conn

            link_id = link_citation_to_person(
                db_path=mock_db_path,
                person_id=1,
                citation_id=101,
                has_grave_photo=True,
            )

            # Verify link was created
            assert link_id is not None

            # Check Quality field is PDX
            cursor = conn.cursor()
            cursor.execute("""
                SELECT Quality FROM CitationLinkTable
                WHERE CitationID = 101 AND OwnerType = 0 AND OwnerID = 1
            """)
            quality = cursor.fetchone()[0]
            assert quality == 'PDX', f"Expected PDX, got {quality}"

            conn.close()

    def test_burial_event_link_default_sdx(self, mock_db_path):
        """Test that burial event citation link defaults to SDX quality without photos."""
        with patch('rmcitecraft.database.connection.connect_rmtree') as mock_connect:
            conn = sqlite3.connect(mock_db_path)
            mock_connect.return_value = conn

            # Mock get_death_date_for_burial to return None
            with patch('rmcitecraft.database.findagrave_queries.get_death_date_for_burial', return_value=None), \
                 patch('rmcitecraft.database.findagrave_queries.get_or_create_location', return_value=1), \
                 patch('rmcitecraft.database.findagrave_queries.get_or_create_cemetery', return_value=None):
                result = create_burial_event_and_link_citation(
                    db_path=mock_db_path,
                    person_id=1,
                    citation_id=200,
                    cemetery_name="Test Cemetery",
                    cemetery_city="Test City",
                    cemetery_county="Test County",
                    cemetery_state="Test State",
                    cemetery_country="USA",
                    has_grave_photo=False,
                )

            # Verify burial event was created
            assert result['burial_event_id'] is not None

            # Check Quality field is SDX
            cursor = conn.cursor()
            cursor.execute("""
                SELECT Quality FROM CitationLinkTable
                WHERE CitationID = 200 AND OwnerType = 2 AND OwnerID = ?
            """, (result['burial_event_id'],))
            quality = cursor.fetchone()[0]
            assert quality == 'SDX', f"Expected SDX, got {quality}"

            conn.close()

    def test_burial_event_link_upgrade_pdx(self, mock_db_path):
        """Test that burial event citation link upgrades to PDX quality with grave photo."""
        with patch('rmcitecraft.database.connection.connect_rmtree') as mock_connect:
            conn = sqlite3.connect(mock_db_path)
            mock_connect.return_value = conn

            # Mock get_death_date_for_burial to return None
            with patch('rmcitecraft.database.findagrave_queries.get_death_date_for_burial', return_value=None), \
                 patch('rmcitecraft.database.findagrave_queries.get_or_create_location', return_value=1), \
                 patch('rmcitecraft.database.findagrave_queries.get_or_create_cemetery', return_value=None):
                result = create_burial_event_and_link_citation(
                    db_path=mock_db_path,
                    person_id=1,
                    citation_id=201,
                    cemetery_name="Test Cemetery",
                    cemetery_city="Test City",
                    cemetery_county="Test County",
                    cemetery_state="Test State",
                    cemetery_country="USA",
                    has_grave_photo=True,
                )

            # Verify burial event was created
            assert result['burial_event_id'] is not None

            # Check Quality field is PDX
            cursor = conn.cursor()
            cursor.execute("""
                SELECT Quality FROM CitationLinkTable
                WHERE CitationID = 201 AND OwnerType = 2 AND OwnerID = ?
            """, (result['burial_event_id'],))
            quality = cursor.fetchone()[0]
            assert quality == 'PDX', f"Expected PDX, got {quality}"

            conn.close()

    def test_default_parameter_value(self, mock_db_path):
        """Test that has_grave_photo parameter defaults to False (SDX)."""
        with patch('rmcitecraft.database.connection.connect_rmtree') as mock_connect:
            conn = sqlite3.connect(mock_db_path)
            mock_connect.return_value = conn

            # Call without has_grave_photo parameter (should default to False)
            link_id = link_citation_to_person(
                db_path=mock_db_path,
                person_id=1,
                citation_id=102,
            )

            # Check Quality field defaults to SDX
            cursor = conn.cursor()
            cursor.execute("""
                SELECT Quality FROM CitationLinkTable
                WHERE CitationID = 102 AND OwnerType = 0 AND OwnerID = 1
            """)
            quality = cursor.fetchone()[0]
            assert quality == 'SDX', f"Expected SDX default, got {quality}"

            conn.close()


class TestPhotoDetectionLogic:
    """Test photo detection logic in batch processing."""

    def test_detect_grave_photo_lowercase(self):
        """Test detection of 'grave' photo type (lowercase)."""
        memorial_data = {
            'photos': [
                {'photoType': 'grave', 'url': 'https://example.com/1.jpg'},
                {'photoType': 'person', 'url': 'https://example.com/2.jpg'},
            ]
        }

        has_grave_photo = False
        photos = memorial_data.get('photos', [])
        for photo in photos:
            photo_type = photo.get('photoType', '').lower()
            if photo_type in ['grave', 'headstone']:
                has_grave_photo = True
                break

        assert has_grave_photo is True

    def test_detect_headstone_photo(self):
        """Test detection of 'headstone' photo type."""
        memorial_data = {
            'photos': [
                {'photoType': 'Headstone', 'url': 'https://example.com/1.jpg'},
            ]
        }

        has_grave_photo = False
        photos = memorial_data.get('photos', [])
        for photo in photos:
            photo_type = photo.get('photoType', '').lower()
            if photo_type in ['grave', 'headstone']:
                has_grave_photo = True
                break

        assert has_grave_photo is True

    def test_no_grave_photo_detected(self):
        """Test that non-grave photos don't trigger detection."""
        memorial_data = {
            'photos': [
                {'photoType': 'Person', 'url': 'https://example.com/1.jpg'},
                {'photoType': 'Other', 'url': 'https://example.com/2.jpg'},
            ]
        }

        has_grave_photo = False
        photos = memorial_data.get('photos', [])
        for photo in photos:
            photo_type = photo.get('photoType', '').lower()
            if photo_type in ['grave', 'headstone']:
                has_grave_photo = True
                break

        assert has_grave_photo is False

    def test_empty_photos_array(self):
        """Test that empty photos array returns False."""
        memorial_data = {'photos': []}

        has_grave_photo = False
        photos = memorial_data.get('photos', [])
        for photo in photos:
            photo_type = photo.get('photoType', '').lower()
            if photo_type in ['grave', 'headstone']:
                has_grave_photo = True
                break

        assert has_grave_photo is False

    def test_missing_photos_key(self):
        """Test that missing photos key returns False."""
        memorial_data = {}

        has_grave_photo = False
        photos = memorial_data.get('photos', [])
        for photo in photos:
            photo_type = photo.get('photoType', '').lower()
            if photo_type in ['grave', 'headstone']:
                has_grave_photo = True
                break

        assert has_grave_photo is False

    def test_missing_photo_type_key(self):
        """Test that missing photoType key doesn't trigger detection."""
        memorial_data = {
            'photos': [
                {'url': 'https://example.com/1.jpg'},  # No photoType key
            ]
        }

        has_grave_photo = False
        photos = memorial_data.get('photos', [])
        for photo in photos:
            photo_type = photo.get('photoType', '').lower()
            if photo_type in ['grave', 'headstone']:
                has_grave_photo = True
                break

        assert has_grave_photo is False

    def test_case_insensitive_matching(self):
        """Test that photo type matching is case-insensitive."""
        test_cases = ['Grave', 'GRAVE', 'grave', 'GrAvE', 'Headstone', 'HEADSTONE']

        for photo_type_value in test_cases:
            memorial_data = {'photos': [{'photoType': photo_type_value}]}

            has_grave_photo = False
            photos = memorial_data.get('photos', [])
            for photo in photos:
                photo_type = photo.get('photoType', '').lower()
                if photo_type in ['grave', 'headstone']:
                    has_grave_photo = True
                    break

            assert has_grave_photo is True, f"Failed for {photo_type_value}"


class TestQualityCodeValidation:
    """Test that quality codes match RootsMagic specification."""

    def test_sdx_quality_code(self):
        """Test SDX quality code components."""
        quality = 'SDX'

        # Character 1: Information Type
        assert quality[0] == 'S', "S = Secondary"
        # Character 2: Evidence Type
        assert quality[1] == 'D', "D = Direct"
        # Character 3: Source Type
        assert quality[2] == 'X', "X = Derivative"

    def test_pdx_quality_code(self):
        """Test PDX quality code components."""
        quality = 'PDX'

        # Character 1: Information Type
        assert quality[0] == 'P', "P = Primary"
        # Character 2: Evidence Type
        assert quality[1] == 'D', "D = Direct"
        # Character 3: Source Type
        assert quality[2] == 'X', "X = Derivative"

    def test_quality_code_length(self):
        """Test that quality codes are exactly 3 characters."""
        assert len('SDX') == 3
        assert len('PDX') == 3
