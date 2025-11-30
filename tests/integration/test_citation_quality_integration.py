"""Integration tests for citation quality assessment using real database."""

import sqlite3
import pytest

from rmcitecraft.database.findagrave_queries import (
    link_citation_to_person,
    create_findagrave_source_and_citation,
    create_burial_event_and_link_citation,
)


@pytest.mark.integration
class TestCitationQualityIntegration:
    """Integration tests for citation quality assessment with real database."""

    def test_person_link_sdx_without_photos(self, tmp_path):
        """Test that person citation link uses SDX quality without grave photos."""
        # Use actual test database
        db_path = 'data/Iiams.rmtree'

        # Find a real person ID
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT PersonID FROM PersonTable LIMIT 1")
        person_id = cursor.fetchone()[0]
        conn.close()

        # Create test source and citation
        result = create_findagrave_source_and_citation(
            db_path=db_path,
            person_id=person_id,
            source_name="Test Find a Grave Source SDX",
            memorial_url="https://www.findagrave.com/memorial/99999901",
            footnote="Test footnote",
            short_footnote="Test short",
            bibliography="Test bib",
            memorial_text="Test memorial",
            source_comment="Test comment",
        )

        citation_id = result['citation_id']

        # Link to person without grave photo
        link_id = link_citation_to_person(
            db_path=db_path,
            person_id=person_id,
            citation_id=citation_id,
            has_grave_photo=False,
        )

        # Verify Quality is SDX
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT Quality FROM CitationLinkTable
            WHERE LinkID = ?
        """, (link_id,))
        quality = cursor.fetchone()[0]
        conn.close()

        assert quality == 'SDX', f"Expected SDX, got {quality}"

    def test_person_link_pdx_with_photos(self, tmp_path):
        """Test that person citation link uses PDX quality with grave photos."""
        # Use actual test database
        db_path = 'data/Iiams.rmtree'

        # Find a real person ID
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT PersonID FROM PersonTable LIMIT 1")
        person_id = cursor.fetchone()[0]
        conn.close()

        # Create test source and citation
        result = create_findagrave_source_and_citation(
            db_path=db_path,
            person_id=person_id,
            source_name="Test Find a Grave Source PDX",
            memorial_url="https://www.findagrave.com/memorial/99999902",
            footnote="Test footnote",
            short_footnote="Test short",
            bibliography="Test bib",
            memorial_text="Test memorial",
            source_comment="Test comment",
        )

        citation_id = result['citation_id']

        # Link to person WITH grave photo
        link_id = link_citation_to_person(
            db_path=db_path,
            person_id=person_id,
            citation_id=citation_id,
            has_grave_photo=True,
        )

        # Verify Quality is PDX
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT Quality FROM CitationLinkTable
            WHERE LinkID = ?
        """, (link_id,))
        quality = cursor.fetchone()[0]
        conn.close()

        assert quality == 'PDX', f"Expected PDX, got {quality}"

    def test_burial_event_link_sdx_without_photos(self, tmp_path):
        """Test that burial event citation link uses SDX quality without grave photos."""
        # Use actual test database
        db_path = 'data/Iiams.rmtree'

        # Find a real person ID
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT PersonID FROM PersonTable LIMIT 1")
        person_id = cursor.fetchone()[0]
        conn.close()

        # Create test source and citation
        result = create_findagrave_source_and_citation(
            db_path=db_path,
            person_id=person_id,
            source_name="Test Find a Grave Burial SDX",
            memorial_url="https://www.findagrave.com/memorial/99999903",
            footnote="Test footnote",
            short_footnote="Test short",
            bibliography="Test bib",
            memorial_text="Test memorial",
            source_comment="Test comment",
        )

        citation_id = result['citation_id']

        # Create burial event without grave photo
        burial_result = create_burial_event_and_link_citation(
            db_path=db_path,
            person_id=person_id,
            citation_id=citation_id,
            cemetery_name="Test Cemetery",
            cemetery_city="Test City",
            cemetery_county="Test County",
            cemetery_state="Test State",
            cemetery_country="USA",
            has_grave_photo=False,
        )

        burial_event_id = burial_result['burial_event_id']

        # Verify Quality is SDX for burial event link
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT Quality FROM CitationLinkTable
            WHERE CitationID = ? AND OwnerType = 2 AND OwnerID = ?
        """, (citation_id, burial_event_id))
        quality = cursor.fetchone()[0]
        conn.close()

        assert quality == 'SDX', f"Expected SDX, got {quality}"

    def test_burial_event_link_pdx_with_photos(self, tmp_path):
        """Test that burial event citation link uses PDX quality with grave photos."""
        # Use actual test database
        db_path = 'data/Iiams.rmtree'

        # Find a real person ID
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT PersonID FROM PersonTable LIMIT 1")
        person_id = cursor.fetchone()[0]
        conn.close()

        # Create test source and citation
        result = create_findagrave_source_and_citation(
            db_path=db_path,
            person_id=person_id,
            source_name="Test Find a Grave Burial PDX",
            memorial_url="https://www.findagrave.com/memorial/99999904",
            footnote="Test footnote",
            short_footnote="Test short",
            bibliography="Test bib",
            memorial_text="Test memorial",
            source_comment="Test comment",
        )

        citation_id = result['citation_id']

        # Create burial event WITH grave photo
        burial_result = create_burial_event_and_link_citation(
            db_path=db_path,
            person_id=person_id,
            citation_id=citation_id,
            cemetery_name="Test Cemetery",
            cemetery_city="Test City",
            cemetery_county="Test County",
            cemetery_state="Test State",
            cemetery_country="USA",
            has_grave_photo=True,
        )

        burial_event_id = burial_result['burial_event_id']

        # Verify Quality is PDX for burial event link
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT Quality FROM CitationLinkTable
            WHERE CitationID = ? AND OwnerType = 2 AND OwnerID = ?
        """, (citation_id, burial_event_id))
        quality = cursor.fetchone()[0]
        conn.close()

        assert quality == 'PDX', f"Expected PDX, got {quality}"

    def test_default_parameter_sdx(self, tmp_path):
        """Test that default parameter value results in SDX quality."""
        # Use actual test database
        db_path = 'data/Iiams.rmtree'

        # Find a real person ID
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT PersonID FROM PersonTable LIMIT 1")
        person_id = cursor.fetchone()[0]
        conn.close()

        # Create test source and citation
        result = create_findagrave_source_and_citation(
            db_path=db_path,
            person_id=person_id,
            source_name="Test Find a Grave Default",
            memorial_url="https://www.findagrave.com/memorial/99999905",
            footnote="Test footnote",
            short_footnote="Test short",
            bibliography="Test bib",
            memorial_text="Test memorial",
            source_comment="Test comment",
        )

        citation_id = result['citation_id']

        # Link to person WITHOUT specifying has_grave_photo (should default to False)
        link_id = link_citation_to_person(
            db_path=db_path,
            person_id=person_id,
            citation_id=citation_id,
            # has_grave_photo parameter omitted (defaults to False)
        )

        # Verify Quality defaults to SDX
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT Quality FROM CitationLinkTable
            WHERE LinkID = ?
        """, (link_id,))
        quality = cursor.fetchone()[0]
        conn.close()

        assert quality == 'SDX', f"Expected SDX default, got {quality}"
