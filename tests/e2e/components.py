"""
Reusable E2E test components for RMCitecraft.

Provides a library of reusable components for building end-to-end tests,
promoting consistency and reducing code duplication across E2E tests.
"""

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class BatchResult:
    """Results from a batch processing operation."""

    session_id: str
    census_year: int
    total_items: int
    completed_count: int
    error_count: int
    duration_seconds: float
    errors: list[dict[str, Any]]


@dataclass
class AnalyticsResult:
    """Results from dashboard analytics validation."""

    year_distribution: dict[int, int]
    state_distribution: dict[str, int]
    county_distribution: dict[str, int]
    status_distribution: dict[str, int]
    error_distribution: dict[str, int]
    total_items: int
    completed: int
    failed: int


class E2ETestHelper:
    """Helper class for E2E test operations."""

    @staticmethod
    def wait_for_condition(
        condition_fn: callable,
        timeout_seconds: int = 30,
        poll_interval: float = 0.5,
        error_message: str = "Condition not met within timeout",
    ) -> bool:
        """
        Wait for a condition to be true.

        Args:
            condition_fn: Function that returns True when condition is met
            timeout_seconds: Maximum time to wait
            poll_interval: Time between checks
            error_message: Error message if timeout occurs

        Returns:
            True if condition met, False if timeout

        Raises:
            TimeoutError: If condition not met within timeout
        """
        start = time.time()
        while time.time() - start < timeout_seconds:
            if condition_fn():
                return True
            time.sleep(poll_interval)

        raise TimeoutError(
            f"{error_message} (waited {timeout_seconds}s, checked every {poll_interval}s)"
        )

    @staticmethod
    def create_test_database(db_path: Path, schema_sql: str = None) -> sqlite3.Connection:
        """
        Create a test database with schema.

        Args:
            db_path: Path to database file
            schema_sql: Optional SQL schema to apply

        Returns:
            Database connection
        """
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        if schema_sql:
            conn.executescript(schema_sql)
            conn.commit()

        logger.info(f"Created test database: {db_path}")
        return conn

    @staticmethod
    def populate_test_census_data(
        conn: sqlite3.Connection,
        num_records: int,
        census_year: int,
        state: str = "Ohio",
        county: str = "Noble",
    ) -> list[int]:
        """
        Populate test database with census citation data.

        Args:
            conn: Database connection
            num_records: Number of test records to create
            census_year: Census year (1790-1950)
            state: US state
            county: County name

        Returns:
            List of created person IDs
        """
        cursor = conn.cursor()
        person_ids = []

        for i in range(num_records):
            # Create person
            cursor.execute("""
                INSERT INTO PersonTable (Surname, Given, BirthYear)
                VALUES (?, ?, ?)
            """, (f"TestFamily{i}", f"TestPerson{i}", 1850 + i))
            person_id = cursor.lastrowid
            person_ids.append(person_id)

            # Create FamilySearch citation placeholder
            source_name = f"Fed Census: {census_year}, {state}, {county} [citing sheet 1, family {i+1}] TestFamily{i}, TestPerson{i}"
            cursor.execute("""
                INSERT INTO SourceTable (Name, TemplateID)
                VALUES (?, 0)
            """, (source_name,))
            source_id = cursor.lastrowid

            # Create citation
            citation_text = f"\"United States Census, {census_year},\" database with images, *FamilySearch* (https://familysearch.org/ark:/61903/1:1:TEST{i} : accessed 21 Nov 2025), TestPerson{i} TestFamily{i}, {county} County, {state}, United States; citing sheet 1, family {i+1}, NARA microfilm publication T623."
            cursor.execute("""
                INSERT INTO CitationTable (SourceID, ActualText)
                VALUES (?, ?)
            """, (source_id, citation_text))

        conn.commit()
        logger.info(f"Created {num_records} test census records for {census_year}")
        return person_ids

    @staticmethod
    def calculate_expected_analytics(
        test_data: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Calculate expected analytics from test data.

        Args:
            test_data: List of test batch items

        Returns:
            Expected analytics values
        """
        year_dist = {}
        state_dist = {}
        status_dist = {}

        for item in test_data:
            year = item.get('census_year', 0)
            state = item.get('state', 'Unknown')
            status = item.get('status', 'unknown')

            year_dist[year] = year_dist.get(year, 0) + 1
            state_dist[state] = state_dist.get(state, 0) + 1
            status_dist[status] = status_dist.get(status, 0) + 1

        return {
            'year_distribution': year_dist,
            'state_distribution': state_dist,
            'status_distribution': status_dist,
            'total_items': len(test_data),
            'completed': status_dist.get('complete', 0) + status_dist.get('completed', 0),
            'failed': status_dist.get('error', 0) + status_dist.get('failed', 0),
        }


class LogAnalyzer:
    """Analyzer for application logs during E2E tests."""

    def __init__(self, log_file_path: Path):
        """
        Initialize log analyzer.

        Args:
            log_file_path: Path to log file to analyze
        """
        self.log_file_path = log_file_path
        self.errors = []
        self.warnings = []
        self.info_messages = []

    def analyze(self) -> dict[str, Any]:
        """
        Analyze log file for errors and warnings.

        Returns:
            Dict with error/warning counts and samples
        """
        if not self.log_file_path.exists():
            logger.warning(f"Log file not found: {self.log_file_path}")
            return {
                'errors': [],
                'warnings': [],
                'error_count': 0,
                'warning_count': 0,
                'sample_errors': [],
                'sample_warnings': [],
            }

        self.errors = []
        self.warnings = []

        with open(self.log_file_path) as f:
            for line in f:
                if 'ERROR' in line or 'Exception' in line:
                    self.errors.append(line.strip())
                elif 'WARNING' in line or 'WARN' in line:
                    self.warnings.append(line.strip())

        return {
            'errors': self.errors,
            'warnings': self.warnings,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings),
            'sample_errors': self.errors[:10] if self.errors else [],
            'sample_warnings': self.warnings[:10] if self.warnings else [],
        }

    def assert_no_critical_errors(self, allowed_error_patterns: list[str] = None):
        """
        Assert that no critical errors occurred during test.

        Args:
            allowed_error_patterns: List of error patterns to ignore (e.g., expected errors)

        Raises:
            AssertionError: If critical errors found
        """
        analysis = self.analyze()

        if allowed_error_patterns:
            # Filter out allowed errors
            critical_errors = [
                err for err in analysis['errors']
                if not any(pattern in err for pattern in allowed_error_patterns)
            ]
        else:
            critical_errors = analysis['errors']

        if critical_errors:
            error_summary = "\n".join(critical_errors[:10])
            raise AssertionError(
                f"Found {len(critical_errors)} critical errors in logs:\n{error_summary}"
            )


class DashboardValidator:
    """Validator for dashboard analytics accuracy."""

    def __init__(self, state_repo):
        """
        Initialize dashboard validator.

        Args:
            state_repo: CensusBatchStateRepository instance
        """
        self.state_repo = state_repo

    def validate_year_distribution(
        self,
        expected: dict[int, int],
        tolerance: float = 0.0
    ) -> bool:
        """
        Validate year distribution analytics.

        Args:
            expected: Expected year distribution {year: count}
            tolerance: Allowed difference percentage (0.0 = exact match)

        Returns:
            True if valid

        Raises:
            AssertionError: If validation fails
        """
        actual = self.state_repo.get_year_distribution()

        for year, expected_count in expected.items():
            actual_count = actual.get(year, 0)
            diff = abs(actual_count - expected_count)
            allowed_diff = int(expected_count * tolerance)

            assert diff <= allowed_diff, (
                f"Year {year}: expected {expected_count}, got {actual_count} "
                f"(diff: {diff}, allowed: {allowed_diff})"
            )

        logger.info(f"✓ Year distribution validated: {actual}")
        return True

    def validate_state_distribution(
        self,
        expected: dict[str, int],
        tolerance: float = 0.0
    ) -> bool:
        """
        Validate state distribution analytics.

        Args:
            expected: Expected state distribution {state: count}
            tolerance: Allowed difference percentage

        Returns:
            True if valid

        Raises:
            AssertionError: If validation fails
        """
        actual = self.state_repo.get_state_distribution()

        for state, expected_count in expected.items():
            actual_count = actual.get(state, 0)
            diff = abs(actual_count - expected_count)
            allowed_diff = int(expected_count * tolerance)

            assert diff <= allowed_diff, (
                f"State {state}: expected {expected_count}, got {actual_count} "
                f"(diff: {diff}, allowed: {allowed_diff})"
            )

        logger.info(f"✓ State distribution validated: {actual}")
        return True

    def validate_master_progress(
        self,
        expected_total: int,
        expected_completed: int,
        expected_failed: int,
        tolerance: float = 0.0
    ) -> bool:
        """
        Validate master progress analytics.

        Args:
            expected_total: Expected total items
            expected_completed: Expected completed count
            expected_failed: Expected failed count
            tolerance: Allowed difference percentage

        Returns:
            True if valid

        Raises:
            AssertionError: If validation fails
        """
        progress = self.state_repo.get_master_progress()

        total_diff = abs(progress['total_items'] - expected_total)
        completed_diff = abs(progress['completed'] - expected_completed)
        failed_diff = abs(progress['failed'] - expected_failed)

        assert total_diff <= int(expected_total * tolerance), (
            f"Total items: expected {expected_total}, got {progress['total_items']}"
        )
        assert completed_diff <= int(expected_completed * tolerance), (
            f"Completed: expected {expected_completed}, got {progress['completed']}"
        )
        assert failed_diff <= int(expected_failed * tolerance), (
            f"Failed: expected {expected_failed}, got {progress['failed']}"
        )

        logger.info(f"✓ Master progress validated: {progress}")
        return True


class BatchProcessor:
    """Helper for processing batches in E2E tests."""

    def __init__(self, state_repo):
        """
        Initialize batch processor.

        Args:
            state_repo: CensusBatchStateRepository instance
        """
        self.state_repo = state_repo

    def create_batch(
        self,
        census_year: int,
        num_items: int,
        state: str = "Ohio",
        county: str = "Noble",
    ) -> str:
        """
        Create a test batch with items.

        Args:
            census_year: Census year
            num_items: Number of items in batch
            state: US state
            county: County name

        Returns:
            Session ID
        """
        session_id = f"test_batch_{census_year}_{datetime.now(timezone.utc).timestamp()}"

        # Create session
        self.state_repo.create_session(
            session_id=session_id,
            total_items=num_items,
            census_year=census_year,
        )

        # Create items
        for i in range(num_items):
            person_id = 1000 + i
            person_name = f"Test Person {i}"

            self.state_repo.create_item(
                session_id=session_id,
                person_id=person_id,
                person_name=person_name,
                census_year=census_year,
                state=state,
                county=county,
            )

        logger.info(f"Created test batch: {session_id} ({num_items} items, year {census_year})")
        return session_id

    def simulate_processing(
        self,
        session_id: str,
        success_rate: float = 0.9,
    ) -> BatchResult:
        """
        Simulate batch processing with controlled success rate.

        Args:
            session_id: Session ID to process
            success_rate: Percentage of items that should succeed (0.0-1.0)

        Returns:
            BatchResult with processing statistics
        """
        start_time = time.time()

        session = self.state_repo.get_session(session_id)
        items = self.state_repo.get_session_items(session_id)

        completed = 0
        errors = 0
        error_list = []

        for i, item in enumerate(items):
            # Simulate success/failure based on rate
            if i / len(items) < success_rate:
                # Success
                self.state_repo.update_item_status(item['id'], 'complete')
                completed += 1
            else:
                # Failure
                error_msg = f"Simulated error for item {item['id']}"
                self.state_repo.update_item_status(item['id'], 'error', error_msg)
                errors += 1
                error_list.append({
                    'item_id': item['id'],
                    'person_id': item['person_id'],
                    'error': error_msg,
                })

        # Update session counts
        self.state_repo.update_session_counts(
            session_id=session_id,
            completed_count=completed,
            error_count=errors,
        )

        duration = time.time() - start_time

        return BatchResult(
            session_id=session_id,
            census_year=session['census_year'],
            total_items=len(items),
            completed_count=completed,
            error_count=errors,
            duration_seconds=duration,
            errors=error_list,
        )
