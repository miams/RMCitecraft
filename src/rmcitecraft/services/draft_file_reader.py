"""Service for reading and validating draft registration CSV/XLSX files."""

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False
    logger.warning("openpyxl not available - XLSX support disabled")

from rmcitecraft.models.draft_record import DraftRecord, ValidationResult


class DraftFileReader:
    """Read and validate CSV/XLSX files containing draft registration data.

    Expected columns (case-insensitive, flexible):
    - rin (optional if names provided)
    - given_name, surname (required)
    - birth_year, death_year (optional but recommended)
    - familysearch_citation (optional)
    - ancestry_url (optional)
    - registration_date, state, county (optional)
    - notes (optional)

    Note: Either familysearch_citation or ancestry_url should be provided.
    """

    # Standard column names (lowercase)
    STANDARD_COLUMNS = {
        'rin', 'given_name', 'surname', 'birth_year', 'death_year',
        'familysearch_citation', 'ancestry_url', 'registration_date', 'state', 'county', 'notes'
    }

    # Column aliases (alternative names)
    COLUMN_ALIASES = {
        'person_id': 'rin',
        'personid': 'rin',
        'id': 'rin',
        'given': 'given_name',
        'first_name': 'given_name',
        'firstname': 'given_name',
        'last_name': 'surname',
        'lastname': 'surname',
        'family_name': 'surname',
        'birth': 'birth_year',
        'birth_yr': 'birth_year',
        'death': 'death_year',
        'death_yr': 'death_year',
        'fs_citation': 'familysearch_citation',
        'citation': 'familysearch_citation',
        'familysearch_url': 'familysearch_citation',
        'ancestry': 'ancestry_url',
        'ancestrylibrary_url': 'ancestry_url',
        'reg_date': 'registration_date',
        'date': 'registration_date',
        'note': 'notes',
    }

    def __init__(self):
        """Initialize the file reader."""
        self._column_mapping: Optional[Dict[str, str]] = None

    def read_file(self, filepath: Path) -> List[DraftRecord]:
        """Read draft registration records from CSV or XLSX file.

        Args:
            filepath: Path to CSV or XLSX file

        Returns:
            List of DraftRecord objects

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is unsupported
        """
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        suffix = filepath.suffix.lower()
        if suffix == '.csv':
            return self._read_csv(filepath)
        elif suffix in ['.xlsx', '.xls']:
            return self._read_xlsx(filepath)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    def _read_csv(self, filepath: Path) -> List[DraftRecord]:
        """Read CSV file."""
        logger.info(f"Reading CSV file: {filepath}")
        records = []

        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)

            # Normalize column names
            if reader.fieldnames:
                reader.fieldnames = [self._normalize_column(col) for col in reader.fieldnames]

            for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 is header)
                try:
                    record = self._parse_row(row, row_num)
                    records.append(record)
                except Exception as e:
                    logger.warning(f"Row {row_num}: Failed to parse - {e}")
                    # Continue processing other rows

        logger.info(f"Read {len(records)} records from CSV")
        return records

    def _read_xlsx(self, filepath: Path) -> List[DraftRecord]:
        """Read XLSX file."""
        if not OPENPYXL_AVAILABLE:
            raise ImportError("openpyxl is required for XLSX files. Install with: pip install openpyxl")

        logger.info(f"Reading XLSX file: {filepath}")
        records = []

        workbook = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        sheet = workbook.active

        # Get headers from first row
        headers = []
        for cell in sheet[1]:
            if cell.value:
                headers.append(self._normalize_column(str(cell.value)))
            else:
                headers.append(None)

        # Read data rows
        for row_num, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            try:
                # Create dict from headers and row values
                row_dict = {}
                for header, value in zip(headers, row):
                    if header and value is not None:
                        row_dict[header] = value

                if row_dict:  # Skip empty rows
                    record = self._parse_row(row_dict, row_num)
                    records.append(record)
            except Exception as e:
                logger.warning(f"Row {row_num}: Failed to parse - {e}")

        workbook.close()
        logger.info(f"Read {len(records)} records from XLSX")
        return records

    def _normalize_column(self, column_name: str) -> str:
        """Normalize column name to standard format.

        Args:
            column_name: Original column name

        Returns:
            Normalized column name
        """
        # Convert to lowercase, remove extra whitespace
        normalized = column_name.lower().strip().replace(' ', '_')

        # Apply aliases
        if normalized in self.COLUMN_ALIASES:
            return self.COLUMN_ALIASES[normalized]

        return normalized

    def _parse_row(self, row: Dict[str, Any], row_number: int) -> DraftRecord:
        """Parse a single row into a DraftRecord.

        Args:
            row: Dictionary of column values
            row_number: Row number (for error reporting)

        Returns:
            DraftRecord object
        """
        def get_value(key: str, default=None):
            """Get value from row, handling None and empty strings."""
            value = row.get(key, default)
            if value is None or (isinstance(value, str) and value.strip() == ''):
                return default
            return value

        def get_int(key: str) -> Optional[int]:
            """Get integer value from row."""
            value = get_value(key)
            if value is None:
                return None
            try:
                return int(value)
            except (ValueError, TypeError):
                return None

        def get_str(key: str) -> Optional[str]:
            """Get string value from row."""
            value = get_value(key)
            if value is None:
                return None
            return str(value).strip() if str(value).strip() else None

        return DraftRecord(
            row_number=row_number,
            rin=get_int('rin'),
            given_name=get_str('given_name') or '',
            surname=get_str('surname') or '',
            birth_year=get_int('birth_year'),
            death_year=get_int('death_year'),
            familysearch_citation=get_str('familysearch_citation') or '',
            ancestry_url=get_str('ancestry_url'),
            registration_date=get_str('registration_date'),
            state=get_str('state'),
            county=get_str('county'),
            notes=get_str('notes'),
        )

    def validate_record(self, record: DraftRecord) -> ValidationResult:
        """Validate a draft record.

        Args:
            record: DraftRecord to validate

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult()

        # Required fields
        if not record.surname:
            result.add_error("Missing surname")

        if not record.given_name:
            result.add_error("Missing given name")

        # Citation field is optional - supports multiple formats:
        # 1. FamilySearch citation text
        # 2. FamilySearch URL (familysearch.org)
        # 3. AncestryLibrary URL (ancestrylibrary.com)
        # 4. "Not found" or explanation text
        # 5. Blank (will skip citation creation)

        # Validate RIN if provided
        if record.rin is not None and record.rin <= 0:
            result.add_error(f"Invalid RIN: {record.rin} (must be positive)")

        # Validate years if provided
        if record.birth_year is not None:
            if record.birth_year < 1700 or record.birth_year > 2100:
                result.add_error(f"Invalid birth year: {record.birth_year}")

        if record.death_year is not None:
            if record.death_year < 1700 or record.death_year > 2100:
                result.add_error(f"Invalid death year: {record.death_year}")

        # Check logical consistency
        if record.birth_year and record.death_year:
            if record.death_year < record.birth_year:
                result.add_error(
                    f"Death year ({record.death_year}) before birth year ({record.birth_year})"
                )

        # Warnings for missing data
        if not record.is_valid_rin and not record.birth_year:
            result.add_warning("No RIN and no birth year - person matching may be difficult")

        # Check if we have any URL source
        has_url = False

        # Classify citation type and add appropriate warnings
        if record.familysearch_citation:
            citation_lower = record.familysearch_citation.lower()
            if 'familysearch.org' in citation_lower or 'ark:/' in citation_lower:
                # FamilySearch URL - good to go
                has_url = True
            elif 'ancestrylibrary.com' in citation_lower:
                result.add_warning("AncestryLibrary URL in familysearch_citation field")
                has_url = True
            elif 'not found' in citation_lower or 'no record' in citation_lower:
                result.add_warning("Draft registration not found")
            else:
                # Has text but not a recognized URL
                result.add_warning("Citation text provided but no URL - may need manual processing")

        # Check ancestry_url field
        if record.ancestry_url:
            if 'ancestrylibrary.com' in record.ancestry_url.lower() or 'ancestry.com' in record.ancestry_url.lower():
                has_url = True
            else:
                result.add_warning("ancestry_url field doesn't contain recognized Ancestry URL")

        # Warn if no URL source available
        if not has_url and not record.familysearch_citation:
            result.add_warning("No URL provided - record will be skipped")

        if not record.state:
            result.add_warning("Missing state information")

        if not record.registration_date:
            result.add_warning("Missing registration date")

        return result

    def preview(self, filepath: Path, limit: int = 10) -> List[DraftRecord]:
        """Read and return first N records from file for preview.

        Args:
            filepath: Path to CSV or XLSX file
            limit: Maximum number of records to return

        Returns:
            List of DraftRecord objects (up to limit)
        """
        all_records = self.read_file(filepath)
        return all_records[:limit]

    def validate_file(self, filepath: Path) -> Dict[str, Any]:
        """Validate entire file and return summary.

        Args:
            filepath: Path to CSV or XLSX file

        Returns:
            Dictionary with validation summary:
            {
                'total_records': int,
                'valid_records': int,
                'invalid_records': int,
                'records_with_warnings': int,
                'validation_results': List[tuple(DraftRecord, ValidationResult)]
            }
        """
        records = self.read_file(filepath)
        validation_results = []
        valid_count = 0
        invalid_count = 0
        warning_count = 0

        for record in records:
            result = self.validate_record(record)
            validation_results.append((record, result))

            if result.is_valid:
                valid_count += 1
                if result.warnings:
                    warning_count += 1
            else:
                invalid_count += 1

        return {
            'total_records': len(records),
            'valid_records': valid_count,
            'invalid_records': invalid_count,
            'records_with_warnings': warning_count,
            'validation_results': validation_results,
        }

    def get_column_mapping(self, headers: List[str]) -> Dict[str, Optional[str]]:
        """Suggest column mapping for non-standard headers.

        Args:
            headers: List of column headers from file

        Returns:
            Dictionary mapping file columns to standard columns
        """
        mapping = {}
        for header in headers:
            normalized = self._normalize_column(header)
            if normalized in self.STANDARD_COLUMNS:
                mapping[header] = normalized
            else:
                mapping[header] = None  # Unmapped column

        return mapping
