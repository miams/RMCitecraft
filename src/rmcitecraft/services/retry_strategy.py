"""
Retry strategy with exponential backoff for Find a Grave batch processing.

Handles transient failures gracefully with configurable retry logic.
"""

import asyncio
import time
from typing import Any, Callable

from loguru import logger


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay_seconds: int = 2,
        max_delay_seconds: int = 60,
        exponential_base: int = 2,
        jitter: bool = True,
    ):
        """Initialize retry configuration.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay_seconds: Initial delay before first retry
            max_delay_seconds: Maximum delay between retries
            exponential_base: Base for exponential backoff (2 = double each time)
            jitter: Add randomness to prevent thundering herd
        """
        self.max_retries = max_retries
        self.base_delay = base_delay_seconds
        self.max_delay = max_delay_seconds
        self.exponential_base = exponential_base
        self.jitter = jitter


class RetryableError(Exception):
    """Base class for errors that should trigger retry."""

    pass


class NonRetryableError(Exception):
    """Base class for errors that should NOT trigger retry."""

    pass


class RetryStrategy:
    """Handle retries with exponential backoff."""

    # Retryable error patterns
    RETRYABLE_PATTERNS = [
        "timeout",
        "page crashed",
        "target crashed",
        "execution context was destroyed",
        "protocol error",
        "session closed",
        "connection closed",
        "connection refused",
        "connection reset",
        "net::err_",
        "network error",
        "dns",
    ]

    # Non-retryable error patterns
    NON_RETRYABLE_PATTERNS = [
        "404",
        "not found",
        "forbidden",
        "unauthorized",
        "memorial does not exist",
        "private memorial",
    ]

    def __init__(self, config: RetryConfig | None = None):
        """Initialize retry strategy.

        Args:
            config: Retry configuration (uses defaults if not provided)
        """
        self.config = config or RetryConfig()
        logger.info(
            f"Initialized retry strategy: max_retries={self.config.max_retries}, "
            f"base_delay={self.config.base_delay}s"
        )

    def should_retry(self, error: Exception, retry_count: int) -> bool:
        """Determine if error is retryable.

        Args:
            error: Exception that occurred
            retry_count: Current retry count

        Returns:
            True if should retry
        """
        # Check retry limit
        if retry_count >= self.config.max_retries:
            logger.info(
                f"Max retries ({self.config.max_retries}) reached, not retrying"
            )
            return False

        # Check for explicit retry/non-retry exceptions
        if isinstance(error, NonRetryableError):
            logger.info(f"NonRetryableError encountered: {error}")
            return False

        if isinstance(error, RetryableError):
            logger.info(f"RetryableError encountered: {error}, will retry")
            return True

        # Check error message for patterns
        error_msg = str(error).lower()

        # Check non-retryable patterns first
        for pattern in self.NON_RETRYABLE_PATTERNS:
            if pattern in error_msg:
                logger.info(f"Non-retryable error pattern '{pattern}' found: {error}")
                return False

        # Check retryable patterns
        for pattern in self.RETRYABLE_PATTERNS:
            if pattern in error_msg:
                logger.info(f"Retryable error pattern '{pattern}' found: {error}")
                return True

        # Unknown error - don't retry by default to be safe
        logger.warning(f"Unknown error type, not retrying: {error}")
        return False

    def get_delay(self, retry_count: int) -> float:
        """Calculate backoff delay for retry.

        Uses exponential backoff: base_delay * (exponential_base ^ retry_count)
        With optional jitter to prevent thundering herd.

        Args:
            retry_count: Current retry count (0-indexed)

        Returns:
            Delay in seconds
        """
        # Calculate exponential backoff
        delay = self.config.base_delay * (self.config.exponential_base ** retry_count)

        # Cap at max delay
        delay = min(delay, self.config.max_delay)

        # Add jitter if enabled (±20% randomness)
        if self.config.jitter:
            import random
            jitter_factor = random.uniform(0.8, 1.2)
            delay = delay * jitter_factor

        return delay

    async def retry_async(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs,
    ) -> Any:
        """Retry an async function with exponential backoff.

        Args:
            func: Async function to retry
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            Last exception if all retries exhausted
        """
        retry_count = 0
        last_exception = None

        while retry_count <= self.config.max_retries:
            try:
                # Attempt operation
                if retry_count > 0:
                    logger.info(
                        f"Retry attempt {retry_count}/{self.config.max_retries} "
                        f"for {func.__name__}"
                    )

                result = await func(*args, **kwargs)

                # Success!
                if retry_count > 0:
                    logger.info(f"Operation succeeded after {retry_count} retries")

                return result

            except Exception as e:
                last_exception = e

                # Check if should retry
                if not self.should_retry(e, retry_count):
                    logger.error(f"Operation failed with non-retryable error: {e}")
                    raise

                # Calculate delay
                delay = self.get_delay(retry_count)

                logger.warning(
                    f"Operation failed (attempt {retry_count + 1}), "
                    f"retrying in {delay:.1f}s: {e}"
                )

                # Wait before retry
                await asyncio.sleep(delay)

                retry_count += 1

        # All retries exhausted
        logger.error(
            f"Operation failed after {self.config.max_retries} retries: "
            f"{last_exception}"
        )
        raise last_exception

    def retry_sync(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs,
    ) -> Any:
        """Retry a synchronous function with exponential backoff.

        Args:
            func: Function to retry
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            Last exception if all retries exhausted
        """
        retry_count = 0
        last_exception = None

        while retry_count <= self.config.max_retries:
            try:
                # Attempt operation
                if retry_count > 0:
                    logger.info(
                        f"Retry attempt {retry_count}/{self.config.max_retries} "
                        f"for {func.__name__}"
                    )

                result = func(*args, **kwargs)

                # Success!
                if retry_count > 0:
                    logger.info(f"Operation succeeded after {retry_count} retries")

                return result

            except Exception as e:
                last_exception = e

                # Check if should retry
                if not self.should_retry(e, retry_count):
                    logger.error(f"Operation failed with non-retryable error: {e}")
                    raise

                # Calculate delay
                delay = self.get_delay(retry_count)

                logger.warning(
                    f"Operation failed (attempt {retry_count + 1}), "
                    f"retrying in {delay:.1f}s: {e}"
                )

                # Wait before retry
                time.sleep(delay)

                retry_count += 1

        # All retries exhausted
        logger.error(
            f"Operation failed after {self.config.max_retries} retries: "
            f"{last_exception}"
        )
        raise last_exception


class RetryContext:
    """Context manager for tracking retry attempts."""

    def __init__(self, operation_name: str, retry_strategy: RetryStrategy):
        """Initialize retry context.

        Args:
            operation_name: Name of operation for logging
            retry_strategy: Retry strategy instance
        """
        self.operation_name = operation_name
        self.retry_strategy = retry_strategy
        self.retry_count = 0
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.success = False
        self.error: Exception | None = None

    def __enter__(self) -> "RetryContext":
        """Start retry context."""
        self.start_time = time.time()
        self.retry_count = 0
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """End retry context and handle retry logic.

        Returns:
            True to suppress exception (will retry), False to propagate
        """
        self.end_time = time.time()

        if exc_type is None:
            # Success
            self.success = True
            if self.retry_count > 0:
                duration = self.end_time - self.start_time
                logger.info(
                    f"{self.operation_name} succeeded after {self.retry_count} "
                    f"retries in {duration:.2f}s"
                )
            return False

        # Error occurred
        self.error = exc_val
        self.success = False

        # Check if should retry
        if self.retry_strategy.should_retry(exc_val, self.retry_count):
            delay = self.retry_strategy.get_delay(self.retry_count)
            logger.warning(
                f"{self.operation_name} failed (attempt {self.retry_count + 1}), "
                f"retrying in {delay:.1f}s: {exc_val}"
            )

            time.sleep(delay)
            self.retry_count += 1

            # Suppress exception to allow retry
            return True
        else:
            # Don't retry, propagate exception
            logger.error(f"{self.operation_name} failed: {exc_val}")
            return False

    @property
    def duration(self) -> float:
        """Get total duration including retries."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0
