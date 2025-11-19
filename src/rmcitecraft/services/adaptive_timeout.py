"""
Adaptive timeout management for Find a Grave batch processing.

Dynamically adjusts timeouts based on observed response times to optimize
for varying network conditions.
"""

import statistics
import time
from collections import deque
from typing import Deque

from loguru import logger


class AdaptiveTimeoutManager:
    """Dynamically adjust timeouts based on observed performance."""

    def __init__(
        self,
        base_timeout_seconds: int = 30,
        window_size: int = 10,
        min_timeout_seconds: int = 15,
        max_timeout_seconds: int = 120,
        percentile: float = 0.95,
    ):
        """Initialize adaptive timeout manager.

        Args:
            base_timeout_seconds: Initial/default timeout value
            window_size: Number of recent requests to consider
            min_timeout_seconds: Minimum allowed timeout
            max_timeout_seconds: Maximum allowed timeout
            percentile: Target percentile for timeout calculation (0.95 = 95th percentile)
        """
        self.base_timeout = base_timeout_seconds
        self.window_size = window_size
        self.min_timeout = min_timeout_seconds
        self.max_timeout = max_timeout_seconds
        self.percentile = percentile

        # Rolling window of recent response times (in seconds)
        self.response_times: Deque[float] = deque(maxlen=window_size)

        # Track successful vs failed operations
        self.success_count = 0
        self.failure_count = 0

        logger.info(
            f"Initialized adaptive timeout manager: "
            f"base={base_timeout_seconds}s, window={window_size}, "
            f"range={min_timeout_seconds}-{max_timeout_seconds}s"
        )

    def record_response_time(self, duration_seconds: float, success: bool = True) -> None:
        """Record page load time.

        Args:
            duration_seconds: Response time in seconds
            success: Whether operation succeeded
        """
        if success:
            self.response_times.append(duration_seconds)
            self.success_count += 1
            logger.debug(f"Recorded response time: {duration_seconds:.2f}s (success)")
        else:
            self.failure_count += 1
            logger.debug(f"Recorded failure at {duration_seconds:.2f}s")

    def get_current_timeout(self) -> int:
        """Calculate timeout based on recent performance.

        Returns:
            Timeout in seconds
        """
        if not self.response_times:
            # No data yet, use base timeout
            return self.base_timeout

        # Calculate statistics from recent response times
        times = list(self.response_times)
        mean = statistics.mean(times)

        if len(times) > 1:
            stdev = statistics.stdev(times)
        else:
            stdev = 0

        # Use mean + 2*stdev to cover ~95% of cases (assuming normal distribution)
        # This is more robust than max() which is sensitive to outliers
        calculated_timeout = mean + (2 * stdev)

        # Add buffer (20% of calculated time, minimum 5 seconds)
        buffer = max(calculated_timeout * 0.2, 5)
        timeout_with_buffer = calculated_timeout + buffer

        # Clamp to min/max range
        timeout = max(self.min_timeout, min(self.max_timeout, timeout_with_buffer))

        logger.debug(
            f"Adaptive timeout: mean={mean:.2f}s, stdev={stdev:.2f}s, "
            f"calculated={calculated_timeout:.2f}s, final={timeout:.0f}s"
        )

        return int(timeout)

    def get_statistics(self) -> dict[str, float]:
        """Get current timeout statistics.

        Returns:
            Dict with timeout statistics
        """
        if not self.response_times:
            return {
                "count": 0,
                "mean": 0,
                "median": 0,
                "min": 0,
                "max": 0,
                "stdev": 0,
                "current_timeout": self.base_timeout,
                "success_rate": 0,
            }

        times = list(self.response_times)
        total_operations = self.success_count + self.failure_count

        return {
            "count": len(times),
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "min": min(times),
            "max": max(times),
            "stdev": statistics.stdev(times) if len(times) > 1 else 0,
            "current_timeout": self.get_current_timeout(),
            "success_rate": self.success_count / total_operations if total_operations > 0 else 0,
        }

    def reset(self) -> None:
        """Reset all statistics and return to base timeout."""
        self.response_times.clear()
        self.success_count = 0
        self.failure_count = 0
        logger.info("Reset adaptive timeout manager")

    def is_performing_well(self, threshold: float = 0.9) -> bool:
        """Check if recent operations are performing well.

        Args:
            threshold: Minimum success rate to consider "performing well"

        Returns:
            True if success rate is above threshold
        """
        total = self.success_count + self.failure_count
        if total == 0:
            return True  # No data yet, assume good

        success_rate = self.success_count / total
        return success_rate >= threshold

    def should_increase_timeout(self, failure_rate_threshold: float = 0.3) -> bool:
        """Determine if timeout should be increased based on failure rate.

        Args:
            failure_rate_threshold: Failure rate above which to increase timeout

        Returns:
            True if timeout should be increased
        """
        total = self.success_count + self.failure_count
        if total == 0:
            return False

        failure_rate = self.failure_count / total
        return failure_rate >= failure_rate_threshold


class TimingContext:
    """Context manager for timing operations and recording to adaptive timeout manager."""

    def __init__(self, timeout_manager: AdaptiveTimeoutManager, operation_name: str = ""):
        """Initialize timing context.

        Args:
            timeout_manager: Adaptive timeout manager instance
            operation_name: Name of operation being timed
        """
        self.timeout_manager = timeout_manager
        self.operation_name = operation_name
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.success = False

    def __enter__(self) -> "TimingContext":
        """Start timing."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """End timing and record result."""
        self.end_time = time.time()

        if self.start_time:
            duration = self.end_time - self.start_time

            # Consider successful if no exception
            self.success = exc_type is None

            # Record to timeout manager
            self.timeout_manager.record_response_time(duration, self.success)

            if self.operation_name:
                status = "succeeded" if self.success else "failed"
                logger.debug(
                    f"{self.operation_name} {status} in {duration:.2f}s"
                )

    @property
    def duration(self) -> float:
        """Get duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0
