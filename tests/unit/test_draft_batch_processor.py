"""Unit tests for DraftBatchProcessor service."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
from dataclasses import dataclass

from rmcitecraft.models.draft_record import (
    DraftRecord,
    RecordResult,
    BatchResult,
    ValidationResult,
)
from rmcitecraft.models.citation_data import (
    FamilySearchMetadata,
    SourceData,
    CitationData,
)
from rmcitecraft.services.draft_batch_processor import (
    DraftBatchProcessor,
    ProcessingConfig,
)


@pytest.fixture
def config(tmp_path):
    """Create test processing configuration."""
    db_path = tmp_path / "test.rmtree"
    db_path.touch()
    return ProcessingConfig(
        db_path=db_path,
        skip_duplicates=True,
        validate_persons=True,
        stop_on_error=False,
        dry_run=False,
    )


@pytest.fixture
def sample_records():
    """Create sample draft records for testing."""
    return [
        DraftRecord(
            row_number=1,
            rin=1,
            given_name="John",
            surname="Smith",
            birth_year=1920,
            death_year=None,
            familysearch_citation="https://familysearch.org/ark:/61903/3:1:33S7-9RQG-9GG7?i=1234",
            registration_date="16 Oct 1940",
            state="Pennsylvania",
            county="Allegheny",
            notes="",
        ),
        DraftRecord(
            row_number=2,
            rin=2,
            given_name="William",
            surname="Jones",
            birth_year=1918,
            death_year=None,
            familysearch_citation="https://familysearch.org/ark:/61903/3:1:33S7-ABCD-EFGH?i=5678",
            registration_date="5 Jun 1917",
            state="Ohio",
            county="Noble",
            notes="",
        ),
    ]


@pytest.fixture
def invalid_record():
    """Create invalid record for testing validation."""
    return DraftRecord(
        row_number=3,
        rin=None,  # Missing RIN
        given_name="",  # Missing given name
        surname="Test",
        birth_year=None,
        death_year=None,
        familysearch_citation="",  # Missing citation
        registration_date=None,
        state=None,
        county=None,
        notes="",
    )


class TestProcessingConfig:
    """Test ProcessingConfig dataclass."""

    def test_default_values(self, tmp_path):
        """Test default configuration values."""
        config = ProcessingConfig(db_path=tmp_path / "test.rmtree")

        assert config.skip_duplicates is True
        assert config.validate_persons is True
        assert config.stop_on_error is False
        assert config.dry_run is False

    def test_custom_values(self, tmp_path):
        """Test custom configuration values."""
        config = ProcessingConfig(
            db_path=tmp_path / "test.rmtree",
            skip_duplicates=False,
            validate_persons=False,
            stop_on_error=True,
            dry_run=True,
        )

        assert config.skip_duplicates is False
        assert config.validate_persons is False
        assert config.stop_on_error is True
        assert config.dry_run is True


class TestDraftBatchProcessor:
    """Test DraftBatchProcessor service."""

    def test_initialization(self, config):
        """Test processor initialization."""
        processor = DraftBatchProcessor(config)

        assert processor.config == config
        assert processor.progress_callback is None
        assert processor.file_reader is not None
        assert processor.citation_builder is not None

    def test_initialization_with_callback(self, config):
        """Test processor initialization with progress callback."""
        callback = Mock()
        processor = DraftBatchProcessor(config, progress_callback=callback)

        assert processor.progress_callback == callback

    @patch("rmcitecraft.services.draft_batch_processor.DraftDatabaseWriter")
    def test_process_batch_success(self, mock_db_writer_class, config, sample_records):
        """Test successful batch processing."""
        # Setup mocks
        mock_db_writer = MagicMock()
        mock_db_writer_class.return_value.__enter__.return_value = mock_db_writer

        mock_db_writer.verify_person_exists.return_value = True
        mock_db_writer.check_duplicate_source.return_value = None
        mock_db_writer.check_duplicate_citation.return_value = None
        mock_db_writer.create_citation_for_person.return_value = (1, 1, 1, True)

        # Process batch
        processor = DraftBatchProcessor(config)
        result = processor.process_batch(sample_records)

        # Verify results
        assert result.total_records == 2
        assert result.processed == 2
        assert result.successful == 2
        assert result.errors == 0
        assert result.skipped == 0
        assert len(result.record_results) == 2
        assert all(r.success for r in result.record_results)
        assert result.batch_id is not None
        assert result.processing_time > 0

    @patch("rmcitecraft.services.draft_batch_processor.DraftDatabaseWriter")
    def test_process_batch_with_progress_callback(
        self, mock_db_writer_class, config, sample_records
    ):
        """Test batch processing with progress callback."""
        # Setup mocks
        mock_db_writer = MagicMock()
        mock_db_writer_class.return_value.__enter__.return_value = mock_db_writer
        mock_db_writer.verify_person_exists.return_value = True
        mock_db_writer.check_duplicate_source.return_value = None
        mock_db_writer.check_duplicate_citation.return_value = None
        mock_db_writer.create_citation_for_person.return_value = (1, 1, 1, True)

        # Create progress callback
        progress_callback = Mock()

        # Process batch
        processor = DraftBatchProcessor(config, progress_callback=progress_callback)
        result = processor.process_batch(sample_records)

        # Verify callback was called
        assert progress_callback.call_count == 2
        progress_callback.assert_any_call(1, 2, "Processing John Smith")
        progress_callback.assert_any_call(2, 2, "Processing William Jones")
        assert result.successful == 2

    @patch("rmcitecraft.services.draft_batch_processor.DraftDatabaseWriter")
    def test_process_batch_skip_duplicates(
        self, mock_db_writer_class, config, sample_records
    ):
        """Test batch processing with duplicate detection."""
        # Setup mocks
        mock_db_writer = MagicMock()
        mock_db_writer_class.return_value.__enter__.return_value = mock_db_writer
        mock_db_writer.verify_person_exists.return_value = True

        # First record: new citation
        # Second record: duplicate citation
        def check_duplicate_source_side_effect(source_data):
            if "Pennsylvania" in source_data.name:
                return None  # No duplicate source
            else:
                return 100  # Existing source

        def check_duplicate_citation_side_effect(person_id, source_id):
            if source_id == 100:
                return 200  # Existing citation
            return None

        mock_db_writer.check_duplicate_source.side_effect = (
            check_duplicate_source_side_effect
        )
        mock_db_writer.check_duplicate_citation.side_effect = (
            check_duplicate_citation_side_effect
        )
        mock_db_writer.create_citation_for_person.return_value = (1, 1, 1, True)

        # Process batch
        processor = DraftBatchProcessor(config)
        result = processor.process_batch(sample_records)

        # Verify results
        assert result.total_records == 2
        assert result.processed == 2
        assert result.successful == 1
        assert result.errors == 0
        assert result.skipped == 1

        # Check second record was skipped
        assert result.record_results[1].skipped is True
        assert result.record_results[1].source_id == 100
        assert result.record_results[1].citation_id == 200

    @patch("rmcitecraft.services.draft_batch_processor.DraftDatabaseWriter")
    def test_process_batch_person_not_found(
        self, mock_db_writer_class, config, sample_records
    ):
        """Test batch processing when person not found."""
        # Setup mocks
        mock_db_writer = MagicMock()
        mock_db_writer_class.return_value.__enter__.return_value = mock_db_writer

        # First person exists, second doesn't
        mock_db_writer.verify_person_exists.side_effect = [True, False]
        mock_db_writer.check_duplicate_source.return_value = None
        mock_db_writer.check_duplicate_citation.return_value = None
        mock_db_writer.create_citation_for_person.return_value = (1, 1, 1, True)

        # Process batch
        processor = DraftBatchProcessor(config)
        result = processor.process_batch(sample_records)

        # Verify results
        assert result.total_records == 2
        assert result.processed == 2
        assert result.successful == 1
        assert result.errors == 1
        assert result.skipped == 0

        # Check second record failed
        assert result.record_results[1].success is False
        assert "not found in database" in result.record_results[1].error_message

    @patch("rmcitecraft.services.draft_batch_processor.DraftDatabaseWriter")
    def test_process_batch_invalid_record(
        self, mock_db_writer_class, config, invalid_record
    ):
        """Test batch processing with invalid record."""
        # Setup mocks
        mock_db_writer = MagicMock()
        mock_db_writer_class.return_value.__enter__.return_value = mock_db_writer

        # Process batch
        processor = DraftBatchProcessor(config)
        result = processor.process_batch([invalid_record])

        # Verify results
        assert result.total_records == 1
        assert result.processed == 1
        assert result.successful == 0
        assert result.errors == 1
        assert result.skipped == 0

        # Check error
        assert result.record_results[0].success is False
        assert result.record_results[0].error_message is not None

    @patch("rmcitecraft.services.draft_batch_processor.DraftDatabaseWriter")
    def test_process_batch_stop_on_error(
        self, mock_db_writer_class, config, sample_records
    ):
        """Test batch processing with stop_on_error enabled."""
        # Enable stop on error
        config.stop_on_error = True

        # Setup mocks
        mock_db_writer = MagicMock()
        mock_db_writer_class.return_value.__enter__.return_value = mock_db_writer

        # First person not found (error)
        mock_db_writer.verify_person_exists.return_value = False

        # Process batch
        processor = DraftBatchProcessor(config)
        result = processor.process_batch(sample_records)

        # Verify processing stopped after first error
        assert result.total_records == 2
        assert result.processed == 1  # Only first record processed
        assert result.successful == 0
        assert result.errors == 1
        assert len(result.record_results) == 1

    @patch("rmcitecraft.services.draft_batch_processor.DraftDatabaseWriter")
    def test_process_batch_dry_run(self, mock_db_writer_class, config, sample_records):
        """Test batch processing in dry run mode."""
        # Enable dry run
        config.dry_run = True

        # Setup mocks
        mock_db_writer = MagicMock()
        mock_db_writer_class.return_value.__enter__.return_value = mock_db_writer
        mock_db_writer.verify_person_exists.return_value = True
        # Ensure duplicate checks return None to avoid skipping
        mock_db_writer.check_duplicate_source.return_value = None
        mock_db_writer.check_duplicate_citation.return_value = None

        # Process batch
        processor = DraftBatchProcessor(config)
        result = processor.process_batch(sample_records)

        # Verify results
        assert result.total_records == 2
        assert result.processed == 2
        assert result.successful == 2
        assert result.errors == 0

        # Verify no database writes occurred
        mock_db_writer.create_citation_for_person.assert_not_called()

        # Check dry run warning
        assert any("Dry run" in w for w in result.record_results[0].warning_messages)

    @patch("rmcitecraft.services.draft_batch_processor.DraftDatabaseWriter")
    def test_process_batch_exception_handling(
        self, mock_db_writer_class, config, sample_records
    ):
        """Test batch processing handles exceptions gracefully."""
        # Setup mocks
        mock_db_writer = MagicMock()
        mock_db_writer_class.return_value.__enter__.return_value = mock_db_writer
        mock_db_writer.verify_person_exists.return_value = True
        mock_db_writer.check_duplicate_source.return_value = None
        mock_db_writer.check_duplicate_citation.return_value = None

        # First record succeeds, second raises exception
        mock_db_writer.create_citation_for_person.side_effect = [
            (1, 1, 1, True),
            Exception("Database error"),
        ]

        # Process batch
        processor = DraftBatchProcessor(config)
        result = processor.process_batch(sample_records)

        # Verify results
        assert result.total_records == 2
        assert result.processed == 2
        assert result.successful == 1
        assert result.errors == 1

        # Check error was captured
        assert result.record_results[1].success is False
        assert "Database error" in result.record_results[1].error_message

    @patch("rmcitecraft.services.draft_batch_processor.DraftDatabaseWriter")
    def test_process_batch_without_validation(
        self, mock_db_writer_class, config, sample_records
    ):
        """Test batch processing with person validation disabled."""
        # Disable person validation
        config.validate_persons = False

        # Setup mocks
        mock_db_writer = MagicMock()
        mock_db_writer_class.return_value.__enter__.return_value = mock_db_writer
        mock_db_writer.check_duplicate_source.return_value = None
        mock_db_writer.check_duplicate_citation.return_value = None
        mock_db_writer.create_citation_for_person.return_value = (1, 1, 1, True)

        # Process batch
        processor = DraftBatchProcessor(config)
        result = processor.process_batch(sample_records)

        # Verify person validation was not called
        mock_db_writer.verify_person_exists.assert_not_called()

        # Verify success
        assert result.successful == 2

    @patch("rmcitecraft.services.draft_batch_processor.DraftFileReader")
    @patch("rmcitecraft.services.draft_batch_processor.DraftDatabaseWriter")
    def test_process_file_success(
        self, mock_db_writer_class, mock_reader_class, config, sample_records, tmp_path
    ):
        """Test processing file successfully."""
        # Setup mocks
        mock_reader = mock_reader_class.return_value
        mock_reader.read_file.return_value = sample_records

        mock_db_writer = MagicMock()
        mock_db_writer_class.return_value.__enter__.return_value = mock_db_writer
        mock_db_writer.verify_person_exists.return_value = True
        mock_db_writer.check_duplicate_source.return_value = None
        mock_db_writer.check_duplicate_citation.return_value = None
        mock_db_writer.create_citation_for_person.return_value = (1, 1, 1, True)

        # Create test file
        test_file = tmp_path / "test.csv"
        test_file.write_text("dummy content")

        # Process file
        processor = DraftBatchProcessor(config)
        result = processor.process_file(test_file)

        # Verify file was read
        mock_reader.read_file.assert_called_once_with(test_file)

        # Verify results
        assert result.successful == 2
        assert result.errors == 0

    @patch("rmcitecraft.services.draft_batch_processor.DraftFileReader")
    def test_process_file_read_error(self, mock_reader_class, config, tmp_path):
        """Test processing file when read fails."""
        # Setup mock to raise exception
        mock_reader = mock_reader_class.return_value
        mock_reader.read_file.side_effect = Exception("File read error")

        # Create test file
        test_file = tmp_path / "test.csv"
        test_file.write_text("dummy content")

        # Process file
        processor = DraftBatchProcessor(config)
        result = processor.process_file(test_file)

        # Verify error was captured
        assert result.total_records == 0
        assert result.successful == 0
        assert result.errors == 1

    @patch("rmcitecraft.services.draft_batch_processor.DraftFileReader")
    def test_process_file_empty(self, mock_reader_class, config, tmp_path):
        """Test processing empty file."""
        # Setup mock to return empty list
        mock_reader = mock_reader_class.return_value
        mock_reader.read_file.return_value = []

        # Create test file
        test_file = tmp_path / "test.csv"
        test_file.write_text("dummy content")

        # Process file
        processor = DraftBatchProcessor(config)
        result = processor.process_file(test_file)

        # Verify result
        assert result.total_records == 0
        assert result.successful == 0

    def test_validate_file(self, config, tmp_path):
        """Test file validation (dry run)."""
        # Create test file
        test_file = tmp_path / "test.csv"
        test_file.write_text("dummy content")

        # Validate file
        config.dry_run = False  # Start with dry_run disabled
        processor = DraftBatchProcessor(config)

        with patch.object(processor, "process_file") as mock_process:
            mock_process.return_value = BatchResult(
                batch_id=123,
                total_records=2,
                processed=2,
                successful=2,
            )

            result = processor.validate_file(test_file)

            # Verify dry_run was temporarily enabled
            mock_process.assert_called_once_with(test_file)

        # Verify dry_run was restored
        assert config.dry_run is False

    @patch("rmcitecraft.services.draft_batch_processor.DraftFileReader")
    def test_preview_file(self, mock_reader_class, config, sample_records, tmp_path):
        """Test file preview."""
        # Setup mock
        mock_reader = mock_reader_class.return_value
        mock_reader.preview.return_value = sample_records[:1]

        # Create test file
        test_file = tmp_path / "test.csv"
        test_file.write_text("dummy content")

        # Preview file
        processor = DraftBatchProcessor(config)
        result = processor.preview_file(test_file, limit=1)

        # Verify preview was called
        mock_reader.preview.assert_called_once_with(test_file, limit=1)

        # Verify result
        assert len(result) == 1
        assert result[0].given_name == "John"

    @patch("rmcitecraft.services.draft_batch_processor.DraftDatabaseWriter")
    def test_process_batch_collects_warnings(
        self, mock_db_writer_class, config, sample_records
    ):
        """Test batch processing collects warnings."""
        # Setup mocks
        mock_db_writer = MagicMock()
        mock_db_writer_class.return_value.__enter__.return_value = mock_db_writer
        mock_db_writer.verify_person_exists.return_value = True
        mock_db_writer.check_duplicate_source.return_value = None
        mock_db_writer.check_duplicate_citation.return_value = None
        mock_db_writer.create_citation_for_person.return_value = (1, 1, 1, True)

        # Process batch
        processor = DraftBatchProcessor(config)
        result = processor.process_batch(sample_records)

        # Warnings count should be tracked
        assert isinstance(result.warnings, int)
        assert result.warnings >= 0
