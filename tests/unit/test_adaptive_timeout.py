"""Unit tests for AdaptiveTimeoutManager."""

import statistics
import time

import pytest

from rmcitecraft.services.adaptive_timeout import AdaptiveTimeoutManager, TimingContext


class TestAdaptiveTimeoutManager:
    """Test AdaptiveTimeoutManager functionality."""

    def test_initialization_with_defaults(self):
        """Test manager initializes with default values."""
        manager = AdaptiveTimeoutManager()

        assert manager.base_timeout == 30
        assert manager.window_size == 10
        assert manager.min_timeout == 15
        assert manager.max_timeout == 120
        assert len(manager.response_times) == 0
        assert manager.success_count == 0
        assert manager.failure_count == 0

    def test_initialization_with_custom_values(self):
        """Test manager initializes with custom values."""
        manager = AdaptiveTimeoutManager(
            base_timeout_seconds=45,
            window_size=20,
            min_timeout_seconds=20,
            max_timeout_seconds=180,
        )

        assert manager.base_timeout == 45
        assert manager.window_size == 20
        assert manager.min_timeout == 20
        assert manager.max_timeout == 180

    def test_get_current_timeout_with_no_data(self):
        """Test timeout returns base value when no response times recorded."""
        manager = AdaptiveTimeoutManager(base_timeout_seconds=30)

        timeout = manager.get_current_timeout()

        assert timeout == 30

    def test_record_response_time_success(self):
        """Test recording successful response time."""
        manager = AdaptiveTimeoutManager()

        manager.record_response_time(5.0, success=True)

        assert len(manager.response_times) == 1
        assert manager.response_times[0] == 5.0
        assert manager.success_count == 1
        assert manager.failure_count == 0

    def test_record_response_time_failure(self):
        """Test recording failed response time."""
        manager = AdaptiveTimeoutManager()

        manager.record_response_time(10.0, success=False)

        # Failures are not added to response times
        assert len(manager.response_times) == 0
        assert manager.success_count == 0
        assert manager.failure_count == 1

    def test_rolling_window_limit(self):
        """Test response times deque respects window size limit."""
        manager = AdaptiveTimeoutManager(window_size=5)

        # Add 10 response times
        for i in range(10):
            manager.record_response_time(float(i), success=True)

        # Only last 5 should be retained
        assert len(manager.response_times) == 5
        assert list(manager.response_times) == [5.0, 6.0, 7.0, 8.0, 9.0]

    def test_get_current_timeout_calculation(self):
        """Test timeout calculation based on response times."""
        manager = AdaptiveTimeoutManager(
            base_timeout_seconds=30,
            min_timeout_seconds=15,
            max_timeout_seconds=120,
        )

        # Add response times: mean=10.0, stdev≈3.16
        response_times = [6.0, 8.0, 10.0, 12.0, 14.0]
        for rt in response_times:
            manager.record_response_time(rt, success=True)

        timeout = manager.get_current_timeout()

        # Expected: mean + 2*stdev + buffer
        # mean=10.0, stdev≈3.16, calculated=10+2*3.16=16.32
        # buffer=max(16.32*0.2, 5)=5, total=21.32
        # Clamped to [15, 120]
        assert 15 <= timeout <= 120
        assert timeout >= 20  # Should be above mean + 2*stdev

    def test_timeout_clamped_to_min(self):
        """Test timeout is clamped to minimum value."""
        manager = AdaptiveTimeoutManager(
            base_timeout_seconds=30,
            min_timeout_seconds=15,
            max_timeout_seconds=120,
        )

        # Add very fast response times
        for _ in range(5):
            manager.record_response_time(0.1, success=True)

        timeout = manager.get_current_timeout()

        # Should be clamped to minimum
        assert timeout == 15

    def test_timeout_clamped_to_max(self):
        """Test timeout is clamped to maximum value."""
        manager = AdaptiveTimeoutManager(
            base_timeout_seconds=30,
            min_timeout_seconds=15,
            max_timeout_seconds=60,
        )

        # Add very slow response times
        for _ in range(5):
            manager.record_response_time(50.0, success=True)

        timeout = manager.get_current_timeout()

        # Should be clamped to maximum
        assert timeout == 60

    def test_get_statistics_no_data(self):
        """Test statistics when no data recorded."""
        manager = AdaptiveTimeoutManager(base_timeout_seconds=30)

        stats = manager.get_statistics()

        assert stats['count'] == 0
        assert stats['mean'] == 0
        assert stats['median'] == 0
        assert stats['min'] == 0
        assert stats['max'] == 0
        assert stats['stdev'] == 0
        assert stats['current_timeout'] == 30
        assert stats['success_rate'] == 0

    def test_get_statistics_with_data(self):
        """Test statistics calculation with response times."""
        manager = AdaptiveTimeoutManager()

        response_times = [5.0, 10.0, 15.0, 20.0, 25.0]
        for rt in response_times:
            manager.record_response_time(rt, success=True)

        stats = manager.get_statistics()

        assert stats['count'] == 5
        assert stats['mean'] == 15.0
        assert stats['median'] == 15.0
        assert stats['min'] == 5.0
        assert stats['max'] == 25.0
        assert stats['stdev'] > 0
        assert stats['success_rate'] == 1.0

    def test_reset(self):
        """Test reset clears all statistics."""
        manager = AdaptiveTimeoutManager()

        # Add some data
        for i in range(5):
            manager.record_response_time(float(i), success=True)

        manager.reset()

        assert len(manager.response_times) == 0
        assert manager.success_count == 0
        assert manager.failure_count == 0

    def test_is_performing_well_no_data(self):
        """Test is_performing_well with no data."""
        manager = AdaptiveTimeoutManager()

        # No data = assume performing well
        assert manager.is_performing_well(threshold=0.9) is True

    def test_is_performing_well_high_success_rate(self):
        """Test is_performing_well with high success rate."""
        manager = AdaptiveTimeoutManager()

        # Record 9 successes, 1 failure
        for _ in range(9):
            manager.record_response_time(10.0, success=True)
        manager.record_response_time(10.0, success=False)

        # Success rate = 9/10 = 0.9
        assert manager.is_performing_well(threshold=0.9) is True
        assert manager.is_performing_well(threshold=0.95) is False

    def test_is_performing_well_low_success_rate(self):
        """Test is_performing_well with low success rate."""
        manager = AdaptiveTimeoutManager()

        # Record 5 successes, 5 failures
        for _ in range(5):
            manager.record_response_time(10.0, success=True)
            manager.record_response_time(10.0, success=False)

        # Success rate = 5/10 = 0.5
        assert manager.is_performing_well(threshold=0.9) is False

    def test_should_increase_timeout_no_data(self):
        """Test should_increase_timeout with no data."""
        manager = AdaptiveTimeoutManager()

        # No data = don't increase
        assert manager.should_increase_timeout(failure_rate_threshold=0.3) is False

    def test_should_increase_timeout_high_failure_rate(self):
        """Test should_increase_timeout with high failure rate."""
        manager = AdaptiveTimeoutManager()

        # Record 3 successes, 7 failures
        for _ in range(3):
            manager.record_response_time(10.0, success=True)
        for _ in range(7):
            manager.record_response_time(10.0, success=False)

        # Failure rate = 7/10 = 0.7
        assert manager.should_increase_timeout(failure_rate_threshold=0.3) is True

    def test_should_increase_timeout_low_failure_rate(self):
        """Test should_increase_timeout with low failure rate."""
        manager = AdaptiveTimeoutManager()

        # Record 9 successes, 1 failure
        for _ in range(9):
            manager.record_response_time(10.0, success=True)
        manager.record_response_time(10.0, success=False)

        # Failure rate = 1/10 = 0.1
        assert manager.should_increase_timeout(failure_rate_threshold=0.3) is False


class TestTimingContext:
    """Test TimingContext context manager."""

    def test_timing_context_success(self):
        """Test timing context records duration on success."""
        manager = AdaptiveTimeoutManager()

        with TimingContext(manager, "test_operation") as ctx:
            time.sleep(0.1)  # Simulate work

        assert ctx.success is True
        assert ctx.duration >= 0.1
        assert len(manager.response_times) == 1
        assert manager.success_count == 1

    def test_timing_context_failure(self):
        """Test timing context records failure on exception."""
        manager = AdaptiveTimeoutManager()

        with pytest.raises(ValueError):
            with TimingContext(manager, "test_operation") as ctx:
                time.sleep(0.1)
                raise ValueError("Test error")

        assert ctx.success is False
        assert ctx.duration >= 0.1
        assert len(manager.response_times) == 0  # Failures not added to times
        assert manager.failure_count == 1

    def test_timing_context_without_operation_name(self):
        """Test timing context works without operation name."""
        manager = AdaptiveTimeoutManager()

        with TimingContext(manager) as ctx:
            time.sleep(0.05)

        assert ctx.success is True
        assert ctx.duration >= 0.05

    def test_timing_context_duration_property(self):
        """Test duration property returns correct value."""
        manager = AdaptiveTimeoutManager()

        with TimingContext(manager) as ctx:
            pass

        # Duration should be >= 0
        assert ctx.duration >= 0
        assert isinstance(ctx.duration, float)
