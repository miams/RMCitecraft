"""Unit tests for DraftFileReader service."""

import pytest
from pathlib import Path
import tempfile
import csv

from rmcitecraft.services.draft_file_reader import DraftFileReader
from rmcitecraft.models.draft_record import DraftRecord


@pytest.fixture
def file_reader():
    """Create a DraftFileReader instance."""
    return DraftFileReader()


@pytest.fixture
def sample_csv_path(tmp_path):
    """Create a sample CSV file for testing."""
    csv_path = tmp_path / "test_draft.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['rin', 'given_name', 'surname', 'birth_year', 'death_year',
                        'familysearch_citation', 'state'])
        writer.writerow([527, 'John', 'Smith', 1918, 1994,
                        'https://familysearch.org/ark:/61903/1:1:ABC123', 'PA'])
        writer.writerow([1234, 'Jane', 'Doe', 1920, 2005,
                        'Pennsylvania, World War II Draft...', 'CA'])
        writer.writerow([5678, 'Bob', 'Johnson', 1915, '',
                        'https://familysearch.org/ark:/61903/1:1:XYZ789', 'OH'])

    return csv_path


@pytest.fixture
def invalid_csv_path(tmp_path):
    """Create a CSV file with invalid data."""
    csv_path = tmp_path / "invalid_draft.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['rin', 'given_name', 'surname', 'familysearch_citation'])
        writer.writerow([-1, '', 'Smith', ''])  # Invalid RIN, missing name and citation
        writer.writerow([999, 'John', '', 'https://familysearch.org/test'])  # Missing surname

    return csv_path


class TestDraftFileReaderInit:
    """Test DraftFileReader initialization."""

    def test_init(self, file_reader):
        """Test basic initialization."""
        assert file_reader is not None
        assert file_reader._column_mapping is None


class TestReadCSV:
    """Test CSV file reading."""

    def test_read_valid_csv(self, file_reader, sample_csv_path):
        """Test reading a valid CSV file."""
        records = file_reader.read_file(sample_csv_path)

        assert len(records) == 3
        assert all(isinstance(r, DraftRecord) for r in records)

        # Check first record
        assert records[0].rin == 527
        assert records[0].given_name == 'John'
        assert records[0].surname == 'Smith'
        assert records[0].birth_year == 1918
        assert records[0].death_year == 1994
        assert 'familysearch.org' in records[0].familysearch_citation
        assert records[0].state == 'PA'

    def test_read_csv_with_aliases(self, file_reader, tmp_path):
        """Test reading CSV with column aliases."""
        csv_path = tmp_path / "aliases.csv"
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['person_id', 'first_name', 'last_name', 'birth', 'url'])
            writer.writerow([123, 'Alice', 'Wonder', 1920, 'https://familysearch.org/test'])

        records = file_reader.read_file(csv_path)
        assert len(records) == 1
        assert records[0].rin == 123
        assert records[0].given_name == 'Alice'
        assert records[0].surname == 'Wonder'
        assert records[0].birth_year == 1920

    def test_read_csv_with_utf8_bom(self, file_reader, tmp_path):
        """Test reading CSV with UTF-8 BOM."""
        csv_path = tmp_path / "bom.csv"
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['rin', 'given_name', 'surname', 'familysearch_citation'])
            writer.writerow([999, 'Test', 'Person', 'https://familysearch.org/test'])

        records = file_reader.read_file(csv_path)
        assert len(records) == 1
        assert records[0].rin == 999

    def test_read_nonexistent_file(self, file_reader):
        """Test reading a nonexistent file."""
        with pytest.raises(FileNotFoundError):
            file_reader.read_file(Path('/nonexistent/file.csv'))

    def test_read_unsupported_format(self, file_reader, tmp_path):
        """Test reading an unsupported file format."""
        txt_path = tmp_path / "test.txt"
        txt_path.write_text("test")

        with pytest.raises(ValueError, match="Unsupported file format"):
            file_reader.read_file(txt_path)


class TestValidateRecord:
    """Test record validation."""

    def test_validate_valid_record(self, file_reader):
        """Test validating a valid record."""
        record = DraftRecord(
            row_number=1,
            rin=527,
            given_name='John',
            surname='Smith',
            birth_year=1918,
            death_year=1994,
            familysearch_citation='https://familysearch.org/ark:/61903/1:1:ABC',
            registration_date='1940-10-16',
            state='PA',
            county='Allegheny',
            notes=None
        )

        result = file_reader.validate_record(record)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_missing_surname(self, file_reader):
        """Test validation fails for missing surname."""
        record = DraftRecord(
            row_number=1, rin=1, given_name='John', surname='',
            birth_year=None, death_year=None,
            familysearch_citation='https://familysearch.org/test',
            registration_date=None, state=None, county=None, notes=None
        )

        result = file_reader.validate_record(record)
        assert not result.is_valid
        assert any('surname' in err.lower() for err in result.errors)

    def test_validate_missing_given_name(self, file_reader):
        """Test validation fails for missing given name."""
        record = DraftRecord(
            row_number=1, rin=1, given_name='', surname='Smith',
            birth_year=None, death_year=None,
            familysearch_citation='https://familysearch.org/test',
            registration_date=None, state=None, county=None, notes=None
        )

        result = file_reader.validate_record(record)
        assert not result.is_valid
        assert any('given name' in err.lower() for err in result.errors)

    def test_validate_missing_citation(self, file_reader):
        """Test validation fails for missing citation."""
        record = DraftRecord(
            row_number=1, rin=1, given_name='John', surname='Smith',
            birth_year=None, death_year=None, familysearch_citation='',
            registration_date=None, state=None, county=None, notes=None
        )

        result = file_reader.validate_record(record)
        assert not result.is_valid
        assert any('citation' in err.lower() for err in result.errors)

    def test_validate_invalid_rin(self, file_reader):
        """Test validation fails for invalid RIN."""
        record = DraftRecord(
            row_number=1, rin=-1, given_name='John', surname='Smith',
            birth_year=None, death_year=None,
            familysearch_citation='https://familysearch.org/test',
            registration_date=None, state=None, county=None, notes=None
        )

        result = file_reader.validate_record(record)
        assert not result.is_valid
        assert any('invalid rin' in err.lower() for err in result.errors)

    def test_validate_invalid_birth_year(self, file_reader):
        """Test validation fails for invalid birth year."""
        record = DraftRecord(
            row_number=1, rin=1, given_name='John', surname='Smith',
            birth_year=1500, death_year=None,
            familysearch_citation='https://familysearch.org/test',
            registration_date=None, state=None, county=None, notes=None
        )

        result = file_reader.validate_record(record)
        assert not result.is_valid
        assert any('birth year' in err.lower() for err in result.errors)

    def test_validate_death_before_birth(self, file_reader):
        """Test validation fails when death year is before birth year."""
        record = DraftRecord(
            row_number=1, rin=1, given_name='John', surname='Smith',
            birth_year=1920, death_year=1910,
            familysearch_citation='https://familysearch.org/test',
            registration_date=None, state=None, county=None, notes=None
        )

        result = file_reader.validate_record(record)
        assert not result.is_valid
        assert any('death year' in err.lower() and 'before' in err.lower()
                  for err in result.errors)

    def test_validate_warnings(self, file_reader):
        """Test validation warnings for missing optional fields."""
        record = DraftRecord(
            row_number=1, rin=None, given_name='John', surname='Smith',
            birth_year=None, death_year=None,
            familysearch_citation='Pennsylvania, World War II Draft...',  # No URL
            registration_date=None, state=None, county=None, notes=None
        )

        result = file_reader.validate_record(record)
        assert result.is_valid  # Still valid despite warnings
        assert len(result.warnings) > 0
        assert any('rin' in warn.lower() or 'birth year' in warn.lower()
                  for warn in result.warnings)


class TestPreview:
    """Test file preview functionality."""

    def test_preview_default_limit(self, file_reader, sample_csv_path):
        """Test preview with default limit."""
        records = file_reader.preview(sample_csv_path)
        assert len(records) == 3  # Sample has 3 records, all returned

    def test_preview_custom_limit(self, file_reader, tmp_path):
        """Test preview with custom limit."""
        # Create CSV with 20 records
        csv_path = tmp_path / "large.csv"
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['rin', 'given_name', 'surname', 'familysearch_citation'])
            for i in range(20):
                writer.writerow([i, f'Person{i}', 'Test', 'https://familysearch.org/test'])

        records = file_reader.preview(csv_path, limit=5)
        assert len(records) == 5


class TestValidateFile:
    """Test full file validation."""

    def test_validate_file_summary(self, file_reader, sample_csv_path):
        """Test validate_file returns correct summary."""
        summary = file_reader.validate_file(sample_csv_path)

        assert summary['total_records'] == 3
        assert summary['valid_records'] >= 0
        assert summary['invalid_records'] >= 0
        assert summary['valid_records'] + summary['invalid_records'] == 3
        assert 'validation_results' in summary

    def test_validate_file_with_errors(self, file_reader, invalid_csv_path):
        """Test validate_file with invalid records."""
        summary = file_reader.validate_file(invalid_csv_path)

        assert summary['total_records'] == 2
        assert summary['invalid_records'] > 0


class TestColumnMapping:
    """Test column mapping functionality."""

    def test_normalize_column(self, file_reader):
        """Test column name normalization."""
        assert file_reader._normalize_column('Given Name') == 'given_name'
        assert file_reader._normalize_column('FIRST_NAME') == 'given_name'
        assert file_reader._normalize_column('person_id') == 'rin'
        assert file_reader._normalize_column('  Surname  ') == 'surname'

    def test_get_column_mapping(self, file_reader):
        """Test getting column mapping suggestions."""
        headers = ['Person ID', 'First Name', 'Last Name', 'Unknown Column']
        mapping = file_reader.get_column_mapping(headers)

        assert mapping['Person ID'] == 'rin'
        assert mapping['First Name'] == 'given_name'
        assert mapping['Last Name'] == 'surname'
        assert mapping['Unknown Column'] is None


class TestDraftRecordProperties:
    """Test DraftRecord model properties."""

    def test_full_name(self):
        """Test full_name property."""
        record = DraftRecord(
            row_number=1, rin=1, given_name='John', surname='Smith',
            birth_year=None, death_year=None, familysearch_citation='test',
            registration_date=None, state=None, county=None, notes=None
        )
        assert record.full_name == 'John Smith'

    def test_is_valid_rin(self):
        """Test is_valid_rin property."""
        record1 = DraftRecord(
            row_number=1, rin=527, given_name='John', surname='Smith',
            birth_year=None, death_year=None, familysearch_citation='test',
            registration_date=None, state=None, county=None, notes=None
        )
        assert record1.is_valid_rin

        record2 = DraftRecord(
            row_number=1, rin=None, given_name='John', surname='Smith',
            birth_year=None, death_year=None, familysearch_citation='test',
            registration_date=None, state=None, county=None, notes=None
        )
        assert not record2.is_valid_rin

        record3 = DraftRecord(
            row_number=1, rin=0, given_name='John', surname='Smith',
            birth_year=None, death_year=None, familysearch_citation='test',
            registration_date=None, state=None, county=None, notes=None
        )
        assert not record3.is_valid_rin

    def test_has_familysearch_url(self):
        """Test has_familysearch_url property."""
        record1 = DraftRecord(
            row_number=1, rin=1, given_name='John', surname='Smith',
            birth_year=None, death_year=None,
            familysearch_citation='https://familysearch.org/ark:/61903/1:1:ABC',
            registration_date=None, state=None, county=None, notes=None
        )
        assert record1.has_familysearch_url

        record2 = DraftRecord(
            row_number=1, rin=1, given_name='John', surname='Smith',
            birth_year=None, death_year=None,
            familysearch_citation='Pennsylvania, World War II Draft...',
            registration_date=None, state=None, county=None, notes=None
        )
        assert not record2.has_familysearch_url
