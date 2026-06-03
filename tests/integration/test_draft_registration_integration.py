"""Integration tests for Draft Registration batch processing.

Tests the complete workflow:
1. File reading (CSV/XLSX)
2. Citation building (Evidence Explained format)
3. Database writing (Source, Citation, CitationLink)
4. Duplicate detection
5. Error handling
"""

import pytest
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

from rmcitecraft.database.connection import connect_rmtree
from rmcitecraft.models.draft_record import DraftRecord
from rmcitecraft.services.draft_batch_processor import (
    DraftBatchProcessor,
    ProcessingConfig,
)
from rmcitecraft.services.draft_file_reader import DraftFileReader
from rmcitecraft.services.draft_citation_builder import DraftCitationBuilder
from rmcitecraft.services.draft_database_writer import DraftDatabaseWriter


@pytest.fixture
def test_db(tmp_path):
    """Create a temporary test database with sample data."""
    # Copy the real database to temporary location
    source_db = Path(__file__).parent.parent.parent / "data" / "Iiams.rmtree"

    if not source_db.exists():
        pytest.skip(f"Test database not found: {source_db}")

    # Create temp copy
    test_db_path = tmp_path / "test.rmtree"
    shutil.copy2(source_db, test_db_path)

    return test_db_path


@pytest.fixture
def sample_csv_file(tmp_path):
    """Create a sample CSV file for testing."""
    csv_path = tmp_path / "sample_draft_records.csv"

    # Create CSV with sample data
    # Using RINs that exist in the test database
    csv_content = """RIN,Given Name,Surname,Birth Year,Death Year,FamilySearch Citation,Registration Date,State,County,Notes
1,George,Iams,1890,1950,https://familysearch.org/ark:/61903/3:1:33S7-9RQG-9GG7,16 Oct 1940,Pennsylvania,Allegheny,Sample WW2 registration
2,William,Iams,1895,,https://familysearch.org/ark:/61903/3:1:33S7-ABCD-EFGH,5 Jun 1917,Ohio,Noble,Sample WW1 registration
"""

    csv_path.write_text(csv_content)
    return csv_path


@pytest.fixture
def invalid_csv_file(tmp_path):
    """Create an invalid CSV file for error testing."""
    csv_path = tmp_path / "invalid_draft_records.csv"

    # Missing required fields, invalid RIN
    csv_content = """RIN,Given Name,Surname
abc,John,Doe
999999,Jane,Smith
,Missing,RIN
"""

    csv_path.write_text(csv_content)
    return csv_path


class TestDraftFileReader:
    """Test file reading functionality."""

    def test_read_csv_file(self, sample_csv_file):
        """Test reading valid CSV file."""
        reader = DraftFileReader()
        records = reader.read_file(sample_csv_file)

        assert len(records) == 2
        assert records[0].given_name == "George"
        assert records[0].surname == "Iams"
        assert records[0].rin == 1
        assert records[0].birth_year == 1890
        assert records[1].given_name == "William"
        assert records[1].rin == 2

    def test_validate_records(self, sample_csv_file):
        """Test record validation."""
        reader = DraftFileReader()
        records = reader.read_file(sample_csv_file)

        # Validate first record
        validation = reader.validate_record(records[0])
        assert validation.is_valid is True

    def test_preview_file(self, sample_csv_file):
        """Test file preview functionality."""
        reader = DraftFileReader()
        preview = reader.preview(sample_csv_file, limit=1)

        assert len(preview) == 1
        assert preview[0].given_name == "George"


class TestDraftCitationBuilder:
    """Test citation building functionality."""

    def test_parse_ww2_url(self):
        """Test parsing WW2 FamilySearch URL."""
        builder = DraftCitationBuilder()

        url = "https://familysearch.org/ark:/61903/3:1:33S7-9RQG-9GG7"
        metadata = builder.parse_familysearch_url(url, state_hint="Pennsylvania")

        assert metadata.ark_id == "61903/3:1:33S7-9RQG-9GG7"
        assert metadata.url == url
        assert metadata.state == "Pennsylvania"
        assert metadata.state_abbr == "PA"

    def test_build_ww2_citation(self):
        """Test building complete WW2 citation."""
        builder = DraftCitationBuilder()

        record = DraftRecord(
            row_number=1,
            rin=1,
            given_name="John",
            surname="Smith",
            birth_year=1920,
            death_year=None,
            familysearch_citation="https://familysearch.org/ark:/61903/3:1:33S7-9RQG-9GG7",
            registration_date="16 Oct 1940",
            state="Pennsylvania",
            county="Allegheny",
            notes="",
        )

        metadata = builder.parse_familysearch_url(
            record.familysearch_citation, state_hint=record.state
        )

        # Build citation
        citation_data = builder.build_citation(record, metadata, source_id=1)

        # Verify citation format
        assert "1940" in citation_data.footnote
        assert "John Smith" in citation_data.footnote
        assert "Allegheny County" in citation_data.footnote
        assert "Pennsylvania" in citation_data.footnote

        # Verify short footnote
        assert "1940" in citation_data.short_footnote
        assert "John Smith" in citation_data.short_footnote
        assert "Allegheny Co." in citation_data.short_footnote
        assert "PA" in citation_data.short_footnote


class TestDraftDatabaseWriter:
    """Test database writing functionality."""

    def test_create_source(self, test_db):
        """Test creating a new source."""
        with DraftDatabaseWriter(test_db, read_only=False) as writer:
            builder = DraftCitationBuilder()

            # Parse metadata and build source
            metadata = builder.parse_familysearch_url(
                "https://familysearch.org/ark:/61903/3:1:33S7-9RQG-9GG7",
                state_hint="Pennsylvania"
            )
            source_data = builder.build_source(metadata)

            # Create source
            source_id, created = writer.create_or_find_source(source_data)

            assert source_id > 0
            assert created is True

            # Verify source was created
            cursor = writer.conn.cursor()
            cursor.execute(
                "SELECT Name, TemplateID FROM SourceTable WHERE SourceID = ?",
                (source_id,)
            )
            result = cursor.fetchone()
            assert result is not None
            assert "Pennsylvania" in result[0]
            assert result[1] == 0  # Free-form template

    def test_duplicate_source_detection(self, test_db):
        """Test duplicate source detection."""
        with DraftDatabaseWriter(test_db, read_only=False) as writer:
            builder = DraftCitationBuilder()

            metadata = builder.parse_familysearch_url(
                "https://familysearch.org/ark:/61903/3:1:33S7-9RQG-9GG7",
                state_hint="Pennsylvania"
            )
            source_data = builder.build_source(metadata)

            # Create source first time
            source_id_1, created_1 = writer.create_or_find_source(source_data)
            assert created_1 is True

            # Try to create same source again
            source_id_2, created_2 = writer.create_or_find_source(source_data)
            assert created_2 is False
            assert source_id_1 == source_id_2

    def test_create_citation_for_person(self, test_db):
        """Test complete workflow: create source, citation, and link."""
        with DraftDatabaseWriter(test_db, read_only=False) as writer:
            builder = DraftCitationBuilder()

            # Use RIN 1 (George Iams) which exists in test database
            person_id = 1

            # Verify person exists
            assert writer.verify_person_exists(person_id) is True

            # Build source and citation
            record = DraftRecord(
                row_number=1,
                rin=person_id,
                given_name="George",
                surname="Iams",
                birth_year=1890,
                death_year=None,
                familysearch_citation="https://familysearch.org/ark:/61903/3:1:33S7-TEST-INTEG",
                registration_date="16 Oct 1940",
                state="Pennsylvania",
                county="Allegheny",
                notes="Integration test",
            )

            metadata = builder.parse_familysearch_url(
                record.familysearch_citation, state_hint=record.state
            )
            source_data = builder.build_source(metadata)
            citation_data = builder.build_citation(record, metadata, source_id=0)

            # Create complete citation
            source_id, citation_id, link_id, source_created = (
                writer.create_citation_for_person(person_id, source_data, citation_data)
            )

            assert source_id > 0
            assert citation_id > 0
            assert link_id > 0
            assert source_created is True

            # Verify citation was created
            cursor = writer.conn.cursor()
            cursor.execute(
                """
                SELECT Footnote, ShortFootnote, Bibliography
                FROM CitationTable
                WHERE CitationID = ?
                """,
                (citation_id,)
            )
            result = cursor.fetchone()
            assert result is not None
            footnote, short_footnote, bibliography = result

            # Verify citation content
            assert "George Iams" in footnote
            assert "1940" in footnote
            assert "PA" in short_footnote


class TestBatchProcessor:
    """Test complete batch processing workflow."""

    def test_process_valid_file(self, test_db, sample_csv_file):
        """Test processing a valid CSV file."""
        config = ProcessingConfig(
            db_path=test_db,
            skip_duplicates=True,
            validate_persons=True,
            stop_on_error=False,
            dry_run=False,
        )

        processor = DraftBatchProcessor(config)
        result = processor.process_file(sample_csv_file)

        # Verify results
        assert result.total_records == 2
        assert result.processed == 2
        assert result.successful >= 1  # At least one should succeed
        assert result.batch_id is not None
        assert result.processing_time > 0

        # Verify database records were created
        with DraftDatabaseWriter(test_db, read_only=True) as writer:
            # Check that citations were created for the persons
            cursor = writer.conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) FROM CitationTable
                WHERE SourceID IN (
                    SELECT SourceID FROM SourceTable
                    WHERE Name LIKE '%Draft Registration%'
                )
                """
            )
            citation_count = cursor.fetchone()[0]
            assert citation_count >= 1

    def test_dry_run_mode(self, test_db, sample_csv_file):
        """Test dry run mode (no database writes)."""
        # Count existing citations before
        with DraftDatabaseWriter(test_db, read_only=True) as writer:
            cursor = writer.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM CitationTable")
            citations_before = cursor.fetchone()[0]

        # Process in dry run mode
        config = ProcessingConfig(
            db_path=test_db,
            dry_run=True,
        )

        processor = DraftBatchProcessor(config)
        result = processor.process_file(sample_csv_file)

        # Verify no errors
        assert result.errors == 0
        assert result.successful == 2

        # Verify no database writes occurred
        with DraftDatabaseWriter(test_db, read_only=True) as writer:
            cursor = writer.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM CitationTable")
            citations_after = cursor.fetchone()[0]
            assert citations_after == citations_before

    def test_skip_duplicates(self, test_db, sample_csv_file):
        """Test duplicate detection during batch processing."""
        config = ProcessingConfig(
            db_path=test_db,
            skip_duplicates=True,
            validate_persons=True,
        )

        processor = DraftBatchProcessor(config)

        # Process file first time
        result1 = processor.process_file(sample_csv_file)
        successful_1 = result1.successful

        # Process same file again
        result2 = processor.process_file(sample_csv_file)

        # Second run should skip all records (duplicates)
        assert result2.skipped >= successful_1

    def test_invalid_rin_handling(self, test_db, tmp_path):
        """Test handling of invalid RINs."""
        # Create CSV with invalid RIN
        csv_path = tmp_path / "invalid_rin.csv"
        csv_content = """RIN,Given Name,Surname,FamilySearch Citation
999999,Invalid,Person,https://familysearch.org/ark:/61903/3:1:33S7-TEST
"""
        csv_path.write_text(csv_content)

        config = ProcessingConfig(
            db_path=test_db,
            validate_persons=True,
        )

        processor = DraftBatchProcessor(config)
        result = processor.process_file(csv_path)

        # Should fail validation
        assert result.errors == 1
        assert result.successful == 0

    def test_stop_on_error(self, test_db, tmp_path):
        """Test stop_on_error configuration."""
        # Create CSV with one invalid and one valid record
        csv_path = tmp_path / "mixed_validity.csv"
        csv_content = """RIN,Given Name,Surname,FamilySearch Citation
999999,Invalid,Person,https://familysearch.org/ark:/61903/3:1:33S7-TEST
1,George,Iams,https://familysearch.org/ark:/61903/3:1:33S7-TEST2
"""
        csv_path.write_text(csv_content)

        config = ProcessingConfig(
            db_path=test_db,
            validate_persons=True,
            stop_on_error=True,
        )

        processor = DraftBatchProcessor(config)
        result = processor.process_file(csv_path)

        # Should stop after first error
        assert result.processed == 1
        assert result.errors == 1


class TestCitationFormat:
    """Test citation formatting against Evidence Explained standards."""

    def test_ww2_citation_format(self):
        """Test WW2 citation follows Evidence Explained format."""
        builder = DraftCitationBuilder()

        record = DraftRecord(
            row_number=1,
            rin=1,
            given_name="John",
            surname="Smith",
            birth_year=1920,
            death_year=None,
            familysearch_citation="https://familysearch.org/ark:/61903/3:1:33S7-9RQG-9GG7",
            registration_date="16 Oct 1940",
            state="Pennsylvania",
            county="Allegheny",
            notes="",
        )

        metadata = builder.parse_familysearch_url(
            record.familysearch_citation, state_hint=record.state
        )
        citation_data = builder.build_citation(record, metadata, source_id=1)

        # Footnote format: Year, location, person name; imaged, collection, FS URL
        footnote = citation_data.footnote
        assert footnote.startswith("1940 U.S. draft registration")
        assert "Allegheny County, Pennsylvania" in footnote
        assert "John Smith" in footnote
        assert "imaged" in footnote
        assert "FamilySearch" in footnote
        assert "https://familysearch.org" in footnote

        # Short footnote format: Abbreviated
        short = citation_data.short_footnote
        assert "1940 U.S. draft reg." in short
        assert "Allegheny Co., PA" in short
        assert "John Smith" in short

    def test_ww1_citation_format(self):
        """Test WW1 citation follows Evidence Explained format."""
        builder = DraftCitationBuilder()

        record = DraftRecord(
            row_number=1,
            rin=1,
            given_name="William",
            surname="Jones",
            birth_year=1895,
            death_year=None,
            familysearch_citation="https://familysearch.org/ark:/61903/3:1:33S7-ABCD-EFGH",
            registration_date="5 Jun 1917",
            state="Ohio",
            county="Noble",
            notes="",
        )

        metadata = builder.parse_familysearch_url(
            record.familysearch_citation, state_hint=record.state
        )
        citation_data = builder.build_citation(record, metadata, source_id=1)

        # Verify WW1 format
        footnote = citation_data.footnote
        assert "1917 U.S. draft registration" in footnote
        assert "Noble County, Ohio" in footnote
        assert "William Jones" in footnote


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
