"""
Database integrity tests for Find a Grave operations.

These tests ensure that records created by RMCitecraft match the schema,
data types, and structure of existing RootsMagic records.
"""

import sqlite3
from pathlib import Path

import pytest

from rmcitecraft.database.connection import connect_rmtree
from rmcitecraft.database.findagrave_queries import (
    create_cemetery_for_existing_location,
    create_findagrave_source_and_citation,
    create_location_and_cemetery,
    create_burial_event_and_link_citation,
)


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


class TestPlaceTableIntegrity:
    """Test that PlaceTable records match existing schema."""

    def test_place_schema_columns(self, db_connection):
        """Verify PlaceTable has expected columns and types."""
        cursor = db_connection.cursor()
        cursor.execute("PRAGMA table_info(PlaceTable)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected = {
            'PlaceID': 'INTEGER',
            'PlaceType': 'INTEGER',
            'Name': 'TEXT',
            'Abbrev': 'TEXT',
            'Normalized': 'TEXT',
            'Latitude': 'INTEGER',
            'Longitude': 'INTEGER',
            'LatLongExact': 'INTEGER',
            'MasterID': 'INTEGER',
            'Note': 'TEXT',
            'Reverse': 'TEXT',
            'fsID': 'INTEGER',
            'anID': 'INTEGER',
            'UTCModDate': 'FLOAT',
        }

        assert columns == expected, f"PlaceTable schema mismatch: {columns}"

    def test_no_null_integer_columns(self, db_connection):
        """Ensure no NULL values in INTEGER columns (critical for RootsMagic)."""
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT PlaceID, Name
            FROM PlaceTable
            WHERE Latitude IS NULL
               OR Longitude IS NULL
               OR LatLongExact IS NULL
               OR MasterID IS NULL
               OR fsID IS NULL
               OR anID IS NULL
        """)

        nulls = cursor.fetchall()
        assert len(nulls) == 0, f"Found {len(nulls)} places with NULL integers: {nulls[:5]}"

    def test_location_record_matches_existing(self, db_connection, test_db_path, tmp_path):
        """Compare newly created location to existing locations."""
        cursor = db_connection.cursor()

        # Get a sample existing location (PlaceType=0)
        cursor.execute("""
            SELECT PlaceType, Abbrev, Latitude, Longitude, LatLongExact,
                   MasterID, Note, fsID, anID
            FROM PlaceTable
            WHERE PlaceType = 0
            AND Latitude = 0
            AND Longitude = 0
            LIMIT 1
        """)
        existing = cursor.fetchone()
        assert existing, "No existing locations found for comparison"

        # Create a test database in temp directory for write test
        test_db = tmp_path / "test.rmtree"
        import shutil
        shutil.copy(test_db_path, test_db)

        # Create new location
        result = create_location_and_cemetery(
            db_path=str(test_db),
            location_name="Test Location, Test County, Test State, Test Country",
            cemetery_name="Test Cemetery",
        )

        # Read back the created location
        test_conn = connect_rmtree(str(test_db))
        test_cursor = test_conn.cursor()
        test_cursor.execute("""
            SELECT PlaceType, Abbrev, Latitude, Longitude, LatLongExact,
                   MasterID, Note, Reverse, fsID, anID, Name
            FROM PlaceTable
            WHERE PlaceID = ?
        """, (result['location_id'],))
        created = test_cursor.fetchone()
        test_conn.close()

        # Compare field by field (excluding Reverse which is name-specific)
        assert created[0] == existing[0], f"PlaceType mismatch: {created[0]} != {existing[0]}"
        assert created[1] == existing[1], f"Abbrev mismatch: {created[1]} != {existing[1]}"
        assert created[2] == existing[2], f"Latitude mismatch: {created[2]} != {existing[2]}"
        assert created[3] == existing[3], f"Longitude mismatch: {created[3]} != {existing[3]}"
        assert created[4] == existing[4], f"LatLongExact mismatch: {created[4]} != {existing[4]}"
        # MasterID should be 0 for locations
        assert created[5] == 0, f"MasterID should be 0 for locations: {created[5]}"
        assert created[6] == existing[6], f"Note mismatch: {created[6]} != {existing[6]}"
        # Verify Reverse is correctly reversed (not comparing to existing since it's name-dependent)
        name = created[10]
        reverse = created[7]
        expected_reverse = ', '.join(reversed([p.strip() for p in name.split(',')]))
        assert reverse == expected_reverse, \
            f"Reverse should be reversed hierarchy: '{reverse}' != '{expected_reverse}'"
        assert created[8] == existing[7], f"fsID mismatch: {created[8]} != {existing[7]}"
        assert created[9] == existing[8], f"anID mismatch: {created[9]} != {existing[8]}"

    def test_cemetery_record_matches_existing(self, db_connection, test_db_path, tmp_path):
        """Compare newly created cemetery to existing cemeteries."""
        cursor = db_connection.cursor()

        # Get a sample existing cemetery (PlaceType=2)
        cursor.execute("""
            SELECT PlaceType, Abbrev, Latitude, Longitude, LatLongExact,
                   Note, Reverse, fsID, anID
            FROM PlaceTable
            WHERE PlaceType = 2
            AND Latitude = 0
            AND Longitude = 0
            LIMIT 1
        """)
        existing = cursor.fetchone()
        assert existing, "No existing cemeteries found for comparison"

        # Create a test database in temp directory
        test_db = tmp_path / "test.rmtree"
        import shutil
        shutil.copy(test_db_path, test_db)

        # Create new cemetery
        result = create_location_and_cemetery(
            db_path=str(test_db),
            location_name="Test Location, Test County, Test State, Test Country",
            cemetery_name="Test Cemetery",
        )

        # Read back the created cemetery
        test_conn = connect_rmtree(str(test_db))
        test_cursor = test_conn.cursor()
        test_cursor.execute("""
            SELECT PlaceType, Abbrev, Latitude, Longitude, LatLongExact,
                   Note, Reverse, fsID, anID
            FROM PlaceTable
            WHERE PlaceID = ?
        """, (result['cemetery_id'],))
        created = test_cursor.fetchone()
        test_conn.close()

        # Compare field by field (excluding MasterID which links to parent)
        assert created[0] == existing[0], f"PlaceType mismatch: {created[0]} != {existing[0]}"
        assert created[1] == existing[1], f"Abbrev mismatch: {created[1]} != {existing[1]}"
        assert created[2] == existing[2], f"Latitude mismatch: {created[2]} != {existing[2]}"
        assert created[3] == existing[3], f"Longitude mismatch: {created[3]} != {existing[3]}"
        assert created[4] == existing[4], f"LatLongExact mismatch: {created[4]} != {existing[4]}"
        assert created[5] == existing[5], f"Note mismatch: {created[5]} != {existing[5]}"
        assert created[6] == existing[6], f"Reverse mismatch: {created[6]} != {existing[6]}"
        assert created[7] == existing[7], f"fsID mismatch: {created[7]} != {existing[8]}"
        assert created[8] == existing[8], f"anID mismatch: {created[8]} != {existing[8]}"


class TestSourceTableIntegrity:
    """Test that SourceTable records match existing schema."""

    def test_source_schema_columns(self, db_connection):
        """Verify SourceTable has expected columns and types."""
        cursor = db_connection.cursor()
        cursor.execute("PRAGMA table_info(SourceTable)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        # Only check columns we use
        assert 'SourceID' in columns and columns['SourceID'] == 'INTEGER'
        assert 'TemplateID' in columns and columns['TemplateID'] == 'INTEGER'
        assert 'Name' in columns and columns['Name'] == 'TEXT'
        assert 'RefNumber' in columns and columns['RefNumber'] == 'TEXT'
        assert 'Comments' in columns and columns['Comments'] == 'TEXT'
        assert 'Fields' in columns and columns['Fields'] == 'BLOB'
        assert 'UTCModDate' in columns and columns['UTCModDate'] == 'FLOAT'

    def test_findagrave_source_matches_existing_freeform(self, db_connection, test_db_path, tmp_path):
        """Compare created Find a Grave source to existing free-form sources."""
        cursor = db_connection.cursor()

        # Get existing free-form source (TemplateID=0)
        cursor.execute("""
            SELECT TemplateID, RefNumber, ActualText, Comments, Fields, UTCModDate
            FROM SourceTable
            WHERE TemplateID = 0
            AND Name LIKE '%Find a Grave%'
            LIMIT 1
        """)
        existing = cursor.fetchone()

        # Create test database
        test_db = tmp_path / "test.rmtree"
        import shutil
        shutil.copy(test_db_path, test_db)

        # Create Find a Grave source
        result = create_findagrave_source_and_citation(
            db_path=str(test_db),
            person_id=1,
            source_name="Test Source - Find a Grave Memorial",
            memorial_url="https://findagrave.com/memorial/12345",
            footnote="Test Footnote",
            short_footnote="Test Short",
            bibliography="Test Bibliography",
            memorial_text="Test Memorial",
            source_comment="Test Comment",
        )

        # Read created source
        test_conn = connect_rmtree(str(test_db))
        test_cursor = test_conn.cursor()
        test_cursor.execute("""
            SELECT TemplateID, RefNumber, ActualText, Comments, Fields, UTCModDate
            FROM SourceTable
            WHERE SourceID = ?
        """, (result['source_id'],))
        created = test_cursor.fetchone()
        test_conn.close()

        # Compare field by field
        if existing:
            assert created[0] == existing[0], f"TemplateID mismatch: {created[0]} != {existing[0]}"
            assert created[1] == existing[1], f"RefNumber mismatch: '{created[1]}' != '{existing[1]}'"
            assert isinstance(created[2], str), f"ActualText should be TEXT, got {type(created[2])}"
            assert isinstance(created[3], str), f"Comments should be TEXT, got {type(created[3])}"
        else:
            # No existing Find a Grave sources - verify basics
            assert created[0] == 0, "TemplateID should be 0 for free-form"
            assert created[1] == '', "RefNumber should be empty for Find a Grave"

        # Verify Fields is XML BLOB
        assert isinstance(created[4], bytes), f"Fields should be bytes, got {type(created[4])}"
        assert created[4].startswith(b'<'), "Fields should start with XML tag"

        # Verify UTCModDate is recent timestamp
        import time
        now = time.time()
        assert abs(created[5] - now) < 60, f"UTCModDate seems wrong: {created[5]} vs now {now}"

    def test_source_xml_fields_structure(self, test_db_path, tmp_path):
        """Verify SourceTable.Fields XML contains all expected citation fields."""
        import shutil
        import xml.etree.ElementTree as ET

        test_db = tmp_path / "test.rmtree"
        shutil.copy(test_db_path, test_db)

        # Create Find a Grave source
        result = create_findagrave_source_and_citation(
            db_path=str(test_db),
            person_id=1,
            source_name="Test Source",
            memorial_url="https://findagrave.com/memorial/12345",
            footnote="<p>Test Footnote</p>",
            short_footnote="Test Short",
            bibliography="Test Bibliography",
            memorial_text="Test Memorial",
            source_comment="Test Comment",
        )

        # Read Fields XML
        conn = connect_rmtree(str(test_db))
        cursor = conn.cursor()
        cursor.execute("SELECT Fields FROM SourceTable WHERE SourceID = ?", (result['source_id'],))
        fields_blob = cursor.fetchone()[0]
        conn.close()

        # Parse XML
        root = ET.fromstring(fields_blob.decode('utf-8'))

        # Verify structure: <Root><Fields><Field><Name>...</Name><Value>...</Value></Field>...</Fields></Root>
        assert root.tag == 'Root', f"Root tag should be 'Root', got '{root.tag}'"

        fields_elem = root.find('Fields')
        assert fields_elem is not None, "Missing <Fields> element"

        # Extract all field names
        field_names = [field.find('Name').text for field in fields_elem.findall('Field')]

        # Verify required fields for free-form citations
        assert 'Footnote' in field_names, "Missing Footnote field in XML"
        assert 'ShortFootnote' in field_names, "Missing ShortFootnote field in XML"
        assert 'Bibliography' in field_names, "Missing Bibliography field in XML"

        # Verify values
        for field in fields_elem.findall('Field'):
            name = field.find('Name').text
            value_elem = field.find('Value')
            assert value_elem is not None, f"Field '{name}' missing <Value> element"


class TestCitationTableIntegrity:
    """Test that CitationTable records match existing schema."""

    def test_citation_schema_columns(self, db_connection):
        """Verify CitationTable has expected columns."""
        cursor = db_connection.cursor()
        cursor.execute("PRAGMA table_info(CitationTable)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert 'CitationID' in columns and columns['CitationID'] == 'INTEGER'
        assert 'SourceID' in columns and columns['SourceID'] == 'INTEGER'
        assert 'Comments' in columns and columns['Comments'] == 'TEXT'
        assert 'ActualText' in columns and columns['ActualText'] == 'TEXT'
        assert 'RefNumber' in columns and columns['RefNumber'] == 'TEXT'
        assert 'Footnote' in columns and columns['Footnote'] == 'TEXT'
        assert 'ShortFootnote' in columns and columns['ShortFootnote'] == 'TEXT'
        assert 'Bibliography' in columns and columns['Bibliography'] == 'TEXT'
        assert 'Fields' in columns and columns['Fields'] == 'BLOB'
        assert 'CitationName' in columns and columns['CitationName'] == 'TEXT'
        assert 'UTCModDate' in columns and columns['UTCModDate'] == 'FLOAT'

    def test_citation_matches_existing(self, db_connection, test_db_path, tmp_path):
        """Compare created citation to existing citations."""
        cursor = db_connection.cursor()

        # Get existing free-form citation
        cursor.execute("""
            SELECT c.SourceID, c.Comments, c.ActualText, c.RefNumber,
                   c.Footnote, c.ShortFootnote, c.Bibliography, c.Fields
            FROM CitationTable c
            JOIN SourceTable s ON c.SourceID = s.SourceID
            WHERE s.TemplateID = 0
            LIMIT 1
        """)
        existing = cursor.fetchone()

        # Create test database
        test_db = tmp_path / "test.rmtree"
        import shutil
        shutil.copy(test_db_path, test_db)

        # Create Find a Grave source and citation
        result = create_findagrave_source_and_citation(
            db_path=str(test_db),
            person_id=1,
            source_name="Test Source",
            memorial_url="https://findagrave.com/memorial/12345",
            footnote="Test Footnote",
            short_footnote="Test Short",
            bibliography="Test Bibliography",
            memorial_text="Test Memorial",
            source_comment="Test Comment",
        )

        # Read created citation
        test_conn = connect_rmtree(str(test_db))
        test_cursor = test_conn.cursor()
        test_cursor.execute("""
            SELECT SourceID, Comments, ActualText, RefNumber,
                   Footnote, ShortFootnote, Bibliography, Fields
            FROM CitationTable
            WHERE CitationID = ?
        """, (result['citation_id'],))
        created = test_cursor.fetchone()
        test_conn.close()

        # Compare structure (values will differ)
        assert created[0] > 0, "SourceID should be valid"
        assert isinstance(created[1], str), f"Comments should be TEXT, got {type(created[1])}"
        assert isinstance(created[2], str), f"ActualText should be TEXT, got {type(created[2])}"
        assert isinstance(created[3], str), f"RefNumber should be TEXT, got {type(created[3])}"

        # For free-form sources (TemplateID=0), Footnote/ShortFootnote/Bibliography
        # should be EMPTY in CitationTable (stored in SourceTable.Fields instead)
        assert created[4] == '', f"Footnote should be empty for TemplateID=0, got '{created[4]}'  "
        assert created[5] == '', f"ShortFootnote should be empty for TemplateID=0, got '{created[5]}'"
        assert created[6] == '', f"Bibliography should be empty for TemplateID=0, got '{created[6]}'"

        assert isinstance(created[7], bytes), f"Fields should be BLOB, got {type(created[7])}"

    def test_citation_link_exists(self, test_db_path, tmp_path):
        """Verify CitationLinkTable records are created correctly."""
        import shutil

        test_db = tmp_path / "test.rmtree"
        shutil.copy(test_db_path, test_db)

        # Create Find a Grave source and citation
        result = create_findagrave_source_and_citation(
            db_path=str(test_db),
            person_id=1,
            source_name="Test Source",
            memorial_url="https://findagrave.com/memorial/12345",
            footnote="Test Footnote",
            short_footnote="Test Short",
            bibliography="Test Bibliography",
            memorial_text="Test Memorial",
            source_comment="Test Comment",
        )

        # The citation should NOT be automatically linked to person
        # (that's handled separately via create_burial_event_and_link_citation)
        conn = connect_rmtree(str(test_db))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM CitationLinkTable
            WHERE CitationID = ?
        """, (result['citation_id'],))

        link_count = cursor.fetchone()[0]
        conn.close()

        # Should have 0 links (links are created by burial event function)
        assert link_count == 0, f"New citation should have 0 links, found {link_count}"


class TestCitationLinkTableIntegrity:
    """Test that CitationLinkTable records match existing schema."""

    def test_citation_link_schema_columns(self, db_connection):
        """Verify CitationLinkTable has expected columns."""
        cursor = db_connection.cursor()
        cursor.execute("PRAGMA table_info(CitationLinkTable)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert 'LinkID' in columns and columns['LinkID'] == 'INTEGER'
        assert 'CitationID' in columns and columns['CitationID'] == 'INTEGER'
        assert 'OwnerType' in columns and columns['OwnerType'] == 'INTEGER'
        assert 'OwnerID' in columns and columns['OwnerID'] == 'INTEGER'
        assert 'SortOrder' in columns and columns['SortOrder'] == 'INTEGER'
        assert 'Quality' in columns and columns['Quality'] == 'TEXT'
        assert 'IsPrivate' in columns and columns['IsPrivate'] == 'INTEGER'
        assert 'Flags' in columns and columns['Flags'] == 'INTEGER'
        assert 'UTCModDate' in columns and columns['UTCModDate'] == 'FLOAT'

    def test_citation_link_to_event_matches_existing(self, db_connection):
        """Compare citation link field values with existing event links."""
        cursor = db_connection.cursor()

        # Get existing Find a Grave citation link to event
        cursor.execute("""
            SELECT cl.LinkID, cl.CitationID, cl.OwnerType, cl.OwnerID,
                   cl.SortOrder, cl.Quality, cl.IsPrivate, cl.Flags, cl.UTCModDate
            FROM CitationLinkTable cl
            JOIN CitationTable c ON cl.CitationID = c.CitationID
            JOIN SourceTable s ON c.SourceID = s.SourceID
            WHERE s.Name LIKE '%Find%Grave%'
            AND cl.OwnerType = 2
            LIMIT 1
        """)
        existing = cursor.fetchone()

        if existing:
            # Verify patterns in existing Find a Grave links
            link_id, citation_id, owner_type, owner_id, sort_order, quality, is_private, flags, utc_mod_date = existing

            assert owner_type == 2, f"Event links should have OwnerType=2, got {owner_type}"
            # Quality should be populated (99.8% of records have it)
            assert quality is not None, "Quality should not be NULL"
            assert quality in ('~~~', 'SDX', '~~S', 'S~~', '~D~', '~DX', 'SD~', 'S~X', 'D~X', 'S~S'), \
                f"Quality should be standard value, got '{quality}'"
            # IsPrivate should be populated
            assert is_private is not None, "IsPrivate should not be NULL"
            assert is_private == 0, f"IsPrivate should be 0, got {is_private}"
            # Flags should be populated
            assert flags is not None, "Flags should not be NULL"
            assert flags == 0, f"Flags should be 0, got {flags}"

    def test_citation_link_field_population(self, db_connection):
        """Verify critical fields are populated in existing links."""
        cursor = db_connection.cursor()

        # Check field population for event links (OwnerType=2)
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN Quality IS NOT NULL AND Quality != '' THEN 1 ELSE 0 END) as has_quality,
                SUM(CASE WHEN IsPrivate IS NOT NULL THEN 1 ELSE 0 END) as has_isprivate,
                SUM(CASE WHEN Flags IS NOT NULL THEN 1 ELSE 0 END) as has_flags
            FROM CitationLinkTable
            WHERE OwnerType = 2
        """)
        row = cursor.fetchone()
        total, has_quality, has_isprivate, has_flags = row

        # These fields should be populated in at least 99% of records
        quality_pct = (has_quality / total) * 100 if total > 0 else 0
        isprivate_pct = (has_isprivate / total) * 100 if total > 0 else 0
        flags_pct = (has_flags / total) * 100 if total > 0 else 0

        assert quality_pct > 99, f"Quality should be populated in >99% of records, got {quality_pct:.1f}%"
        assert isprivate_pct > 99, f"IsPrivate should be populated in >99% of records, got {isprivate_pct:.1f}%"
        assert flags_pct > 99, f"Flags should be populated in >99% of records, got {flags_pct:.1f}%"

    def test_our_citation_links_match_existing_pattern(self, test_db_path, tmp_path, db_connection):
        """Verify our created citation links match existing RootsMagic patterns."""
        import shutil
        from rmcitecraft.database.findagrave_queries import get_utc_mod_date

        # Get a real person with death date
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT e.OwnerID, n.Surname, n.Given
            FROM EventTable e
            JOIN NameTable n ON e.OwnerID = n.OwnerID
            WHERE e.EventType = 2
            AND e.Date IS NOT NULL
            AND e.Date != ''
            LIMIT 1
        """)
        person_row = cursor.fetchone()
        assert person_row, "Need a person with death date for test"
        person_id, surname, given = person_row

        # Create test database
        test_db = tmp_path / "test.rmtree"
        shutil.copy(test_db_path, test_db)

        # Pre-create a location for the test to match against
        temp_conn = connect_rmtree(str(test_db))
        temp_cursor = temp_conn.cursor()

        location_name = "Test City, Test, Test State, Test Country"
        location_parts = [part.strip() for part in location_name.split(',')]
        reverse_name = ', '.join(reversed(location_parts))
        utc_mod_date = get_utc_mod_date()

        temp_cursor.execute("""
            INSERT INTO PlaceTable (
                PlaceType, Name, Abbrev, Normalized,
                Latitude, Longitude, LatLongExact, MasterID,
                Note, Reverse, fsID, anID, UTCModDate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            0, location_name, '', location_name,
            0, 0, 0, 0, '', reverse_name, 0, 0, utc_mod_date
        ))
        temp_conn.commit()
        temp_conn.close()

        # Create source and citation
        source_result = create_findagrave_source_and_citation(
            db_path=str(test_db),
            person_id=person_id,
            source_name=f"Test Source - {given} {surname}",
            memorial_url="https://findagrave.com/memorial/12345",
            footnote="Test Footnote",
            short_footnote="Test Short",
            bibliography="Test Bibliography",
            memorial_text="Test Memorial",
            source_comment="Test Comment",
        )

        # Create burial event with citation link
        burial_result = create_burial_event_and_link_citation(
            db_path=str(test_db),
            person_id=person_id,
            citation_id=source_result['citation_id'],
            cemetery_name="Test Cemetery",
            cemetery_city="Test City",
            cemetery_county="Test County",
            cemetery_state="Test State",
            cemetery_country="Test Country",
        )

        # Verify the citation link was created correctly
        conn = connect_rmtree(str(test_db))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT LinkID, CitationID, OwnerType, OwnerID, SortOrder,
                   Quality, IsPrivate, Flags, UTCModDate
            FROM CitationLinkTable
            WHERE CitationID = ?
            AND OwnerType = 2
        """, (source_result['citation_id'],))
        link = cursor.fetchone()

        assert link is not None, "Citation link to event not found"

        link_id, citation_id, owner_type, owner_id, sort_order, quality, is_private, flags, utc_mod_date = link

        # Verify all fields match RootsMagic patterns
        assert owner_type == 2, f"OwnerType should be 2 (Event), got {owner_type}"
        assert owner_id == burial_result['burial_event_id'], \
            f"OwnerID should be {burial_result['burial_event_id']}, got {owner_id}"

        # CRITICAL: These fields are populated in 99.8% of existing records
        assert quality is not None, "Quality should not be NULL (99.8% of records have it)"
        assert quality in ('~~~', 'SDX', '~~S', 'S~~', '~D~', '~DX', 'SD~', 'S~X', 'D~X', 'S~S'), \
            f"Quality should be standard value, got '{quality}'"

        assert is_private is not None, "IsPrivate should not be NULL (99.8% of records have it)"
        assert is_private == 0, f"IsPrivate should be 0, got {is_private}"

        assert flags is not None, "Flags should not be NULL (99.8% of records have it)"
        assert flags == 0, f"Flags should be 0, got {flags}"

        # SortOrder can be NULL or 0 (47% have 0, 53% have NULL)
        # We use 0 for consistency with recent records
        assert sort_order == 0, f"SortOrder should be 0, got {sort_order}"

        # UTCModDate should be recent timestamp
        import time
        assert utc_mod_date is not None, "UTCModDate should not be NULL"
        assert abs(utc_mod_date - time.time()) < 60, \
            f"UTCModDate should be recent timestamp, got {utc_mod_date}"

        conn.close()


class TestEventTableIntegrity:
    """Test that EventTable records match existing schema."""

    def test_event_schema_columns(self, db_connection):
        """Verify EventTable has expected columns."""
        cursor = db_connection.cursor()
        cursor.execute("PRAGMA table_info(EventTable)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert 'EventID' in columns and columns['EventID'] == 'INTEGER'
        assert 'EventType' in columns and columns['EventType'] == 'INTEGER'
        assert 'OwnerType' in columns and columns['OwnerType'] == 'INTEGER'
        assert 'OwnerID' in columns and columns['OwnerID'] == 'INTEGER'
        assert 'Date' in columns and columns['Date'] == 'TEXT'
        assert 'SortDate' in columns and columns['SortDate'] == 'BIGINT'  # BIGINT, not INTEGER
        assert 'PlaceID' in columns and columns['PlaceID'] == 'INTEGER'
        assert 'SiteID' in columns and columns['SiteID'] == 'INTEGER'
        assert 'Details' in columns and columns['Details'] == 'TEXT'
        assert 'UTCModDate' in columns and columns['UTCModDate'] == 'FLOAT'

    def test_burial_event_matches_existing(self, db_connection):
        """Compare burial event structure to existing events."""
        cursor = db_connection.cursor()

        # Get existing burial event (EventType=4)
        cursor.execute("""
            SELECT EventType, OwnerType, Details, SiteID
            FROM EventTable
            WHERE EventType = 4
            LIMIT 1
        """)
        existing = cursor.fetchone()

        if existing:
            # Verify our burial events will match this structure
            assert existing[0] == 4, "Burial events should have EventType=4"
            assert existing[1] == 0, "Person-owned events should have OwnerType=0"
            # Details should be empty per user request
            # SiteID should be cemetery PlaceID

    def test_burial_event_creation_full_workflow(self, db_connection, test_db_path, tmp_path):
        """Test full burial event creation with places and citation link."""
        import shutil
        from rmcitecraft.database.findagrave_queries import get_utc_mod_date

        # Get a real person with death date
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT e.OwnerID, n.Surname, n.Given
            FROM EventTable e
            JOIN NameTable n ON e.OwnerID = n.OwnerID
            WHERE e.EventType = 2
            AND e.Date IS NOT NULL
            AND e.Date != ''
            LIMIT 1
        """)
        person_row = cursor.fetchone()
        assert person_row, "Need a person with death date for test"
        person_id, surname, given = person_row

        # Create test database
        test_db = tmp_path / "test.rmtree"
        shutil.copy(test_db_path, test_db)

        # Pre-create a location for the test to match against
        # This ensures we don't hit the "needs approval" path
        # NOTE: Function normalizes county by removing " County" suffix
        temp_conn = connect_rmtree(str(test_db))
        temp_cursor = temp_conn.cursor()

        # Build location_name the same way the function does (with normalized county)
        location_name = "Test City, Test, Test State, Test Country"  # "Test" not "Test County"
        location_parts = [part.strip() for part in location_name.split(',')]
        reverse_name = ', '.join(reversed(location_parts))
        utc_mod_date = get_utc_mod_date()

        temp_cursor.execute("""
            INSERT INTO PlaceTable (
                PlaceType, Name, Abbrev, Normalized,
                Latitude, Longitude, LatLongExact, MasterID,
                Note, Reverse, fsID, anID, UTCModDate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            0, location_name, '', location_name,
            0, 0, 0, 0, '', reverse_name, 0, 0, utc_mod_date
        ))
        temp_conn.commit()
        temp_conn.close()

        # Create source and citation first
        source_result = create_findagrave_source_and_citation(
            db_path=str(test_db),
            person_id=person_id,
            source_name=f"Test Source - {given} {surname}",
            memorial_url="https://findagrave.com/memorial/12345",
            footnote="Test Footnote",
            short_footnote="Test Short",
            bibliography="Test Bibliography",
            memorial_text="Test Memorial",
            source_comment="Test Comment",
        )

        # Create burial event with place and cemetery
        burial_result = create_burial_event_and_link_citation(
            db_path=str(test_db),
            person_id=person_id,
            citation_id=source_result['citation_id'],
            cemetery_name="Test Cemetery",
            cemetery_city="Test City",
            cemetery_county="Test County",
            cemetery_state="Test State",
            cemetery_country="Test Country",
        )

        # Verify burial event was created
        conn = connect_rmtree(str(test_db))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT EventType, OwnerType, OwnerID, PlaceID, SiteID, Details
            FROM EventTable
            WHERE EventID = ?
        """, (burial_result['burial_event_id'],))
        event = cursor.fetchone()

        assert event is not None, "Burial event not found"
        assert event[0] == 4, f"EventType should be 4 (burial), got {event[0]}"
        assert event[1] == 0, f"OwnerType should be 0 (person), got {event[1]}"
        assert event[2] == person_id, f"OwnerID should be {person_id}, got {event[2]}"
        assert event[3] > 0, f"PlaceID should be set, got {event[3]}"
        assert event[4] > 0, f"SiteID should be set (cemetery), got {event[4]}"
        assert event[5] == '', f"Details should be empty, got '{event[5]}'"

        # Verify citation is linked to event
        cursor.execute("""
            SELECT OwnerType, OwnerID, CitationID
            FROM CitationLinkTable
            WHERE CitationID = ?
            AND OwnerType = 2
        """, (source_result['citation_id'],))
        link = cursor.fetchone()

        assert link is not None, "Citation link not found"
        assert link[0] == 2, f"OwnerType should be 2 (event), got {link[0]}"
        assert link[1] == burial_result['burial_event_id'], \
            f"OwnerID should be {burial_result['burial_event_id']}, got {link[1]}"
        assert link[2] == source_result['citation_id'], \
            f"CitationID should be {source_result['citation_id']}, got {link[2]}"

        # Verify place and cemetery were created correctly
        cursor.execute("""
            SELECT PlaceType, Name, MasterID
            FROM PlaceTable
            WHERE PlaceID = ?
        """, (event[3],))
        location = cursor.fetchone()

        assert location is not None, "Location not found"
        assert location[0] == 0, f"PlaceType should be 0 (location), got {location[0]}"
        assert location[2] == 0, f"Location MasterID should be 0, got {location[2]}"

        cursor.execute("""
            SELECT PlaceType, Name, MasterID
            FROM PlaceTable
            WHERE PlaceID = ?
        """, (event[4],))
        cemetery = cursor.fetchone()

        assert cemetery is not None, "Cemetery not found"
        assert cemetery[0] == 2, f"PlaceType should be 2 (cemetery), got {cemetery[0]}"
        assert cemetery[2] == event[3], \
            f"Cemetery MasterID should be {event[3]} (location), got {cemetery[2]}"

        conn.close()


class TestUTCModDateConsistency:
    """Test that UTCModDate is set correctly."""

    def test_utc_mod_date_is_timestamp(self, db_connection):
        """Verify UTCModDate is Unix timestamp (seconds since epoch)."""
        cursor = db_connection.cursor()

        # Check recent records
        cursor.execute("""
            SELECT UTCModDate
            FROM PlaceTable
            WHERE UTCModDate > 0
            ORDER BY PlaceID DESC
            LIMIT 10
        """)

        for row in cursor.fetchall():
            utc_mod_date = row[0]
            # Unix timestamp should be > 1 billion (after 2001)
            # and < 3 billion (before 2065)
            assert 1_000_000_000 < utc_mod_date < 3_000_000_000, \
                f"UTCModDate looks invalid: {utc_mod_date}"


class TestForeignKeyIntegrity:
    """Test that foreign key relationships are valid."""

    def test_cemetery_master_id_references_location(self, db_connection):
        """Verify cemetery MasterID points to valid location."""
        cursor = db_connection.cursor()

        # Find cemeteries with MasterID set
        cursor.execute("""
            SELECT c.PlaceID, c.Name, c.MasterID, p.PlaceID, p.Name
            FROM PlaceTable c
            LEFT JOIN PlaceTable p ON c.MasterID = p.PlaceID
            WHERE c.PlaceType = 2
            AND c.MasterID > 0
        """)

        for row in cursor.fetchall():
            cem_id, cem_name, master_id, loc_id, loc_name = row
            assert loc_id is not None, \
                f"Cemetery {cem_id} ({cem_name}) has MasterID {master_id} but location doesn't exist"
            # Parent should be a location (PlaceType=0)
            cursor.execute("SELECT PlaceType FROM PlaceTable WHERE PlaceID = ?", (master_id,))
            parent_type = cursor.fetchone()[0]
            assert parent_type == 0, \
                f"Cemetery {cem_id} MasterID should point to location (PlaceType=0), got {parent_type}"

    def test_event_place_id_exists(self, db_connection):
        """Verify Event PlaceID points to valid place."""
        cursor = db_connection.cursor()

        cursor.execute("""
            SELECT e.EventID, e.PlaceID, p.PlaceID
            FROM EventTable e
            LEFT JOIN PlaceTable p ON e.PlaceID = p.PlaceID
            WHERE e.PlaceID > 0
        """)

        for row in cursor.fetchall():
            event_id, event_place_id, place_id = row
            assert place_id is not None, \
                f"Event {event_id} has PlaceID {event_place_id} but place doesn't exist"

    def test_citation_source_id_exists(self, db_connection):
        """Verify Citation SourceID points to valid source."""
        cursor = db_connection.cursor()

        cursor.execute("""
            SELECT c.CitationID, c.SourceID, s.SourceID
            FROM CitationTable c
            LEFT JOIN SourceTable s ON c.SourceID = s.SourceID
            WHERE c.SourceID > 0
        """)

        for row in cursor.fetchall():
            citation_id, citation_source_id, source_id = row
            assert source_id is not None, \
                f"Citation {citation_id} has SourceID {citation_source_id} but source doesn't exist"


class TestDataTypeConsistency:
    """Test that data types match expected RootsMagic types."""

    def test_place_id_is_integer(self, db_connection):
        """Ensure PlaceID is always INTEGER."""
        cursor = db_connection.cursor()
        cursor.execute("SELECT PlaceID, typeof(PlaceID) FROM PlaceTable LIMIT 100")

        for row in cursor.fetchall():
            place_id, type_name = row
            assert type_name == 'integer', f"PlaceID {place_id} has type {type_name}, expected integer"

    def test_latitude_longitude_are_integers(self, db_connection):
        """Ensure Latitude/Longitude are always INTEGER (not NULL)."""
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT PlaceID, typeof(Latitude), typeof(Longitude)
            FROM PlaceTable
            LIMIT 100
        """)

        for row in cursor.fetchall():
            place_id, lat_type, lon_type = row
            assert lat_type == 'integer', f"PlaceID {place_id} Latitude has type {lat_type}"
            assert lon_type == 'integer', f"PlaceID {place_id} Longitude has type {lon_type}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
