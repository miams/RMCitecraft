"""Unit tests for RetryStrategy."""

import asyncio
import time

import pytest

from rmcitecraft.services.retry_strategy import (
    NonRetryableError,
    RetryableError,
    RetryConfig,
    RetryStrategy,
)


class TestRetryConfig:
    """Test RetryConfig initialization."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.base_delay == 2
        assert config.max_delay == 60
        assert config.exponential_base == 2
        assert config.jitter is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RetryConfig(
            max_retries=5,
            base_delay_seconds=1,
            max_delay_seconds=30,
            exponential_base=3,
            jitter=False,
        )

        assert config.max_retries == 5
        assert config.base_delay == 1
        assert config.max_delay == 30
        assert config.exponential_base == 3
        assert config.jitter is False


class TestRetryStrategy:
    """Test RetryStrategy functionality."""

    def test_initialization_default_config(self):
        """Test strategy initializes with default config."""
        strategy = RetryStrategy()

        assert strategy.config.max_retries == 3
        assert strategy.config.base_delay == 2

    def test_initialization_custom_config(self):
        """Test strategy initializes with custom config."""
        config = RetryConfig(max_retries=5, base_delay_seconds=1)
        strategy = RetryStrategy(config)

        assert strategy.config.max_retries == 5
        assert strategy.config.base_delay == 1

    def test_should_retry_max_retries_reached(self):
        """Test should_retry returns False when max retries reached."""
        strategy = RetryStrategy(RetryConfig(max_retries=3))

        # Use a retryable error pattern
        error = Exception("timeout occurred")

        # Retry count 0, 1, 2 should retry
        assert strategy.should_retry(error, 0) is True
        assert strategy.should_retry(error, 1) is True
        assert strategy.should_retry(error, 2) is True

        # Retry count 3 (max reached) should not retry
        assert strategy.should_retry(error, 3) is False

    def test_should_retry_non_retryable_error(self):
        """Test should_retry returns False for NonRetryableError."""
        strategy = RetryStrategy()

        error = NonRetryableError("non-retryable error")

        assert strategy.should_retry(error, 0) is False

    def test_should_retry_retryable_error(self):
        """Test should_retry returns True for RetryableError."""
        strategy = RetryStrategy()

        error = RetryableError("retryable error")

        assert strategy.should_retry(error, 0) is True

    def test_should_retry_non_retryable_patterns(self):
        """Test should_retry detects non-retryable error patterns."""
        strategy = RetryStrategy()

        non_retryable_errors = [
            Exception("404 not found"),
            Exception("memorial does not exist"),
            Exception("forbidden access"),
            Exception("unauthorized request"),
            Exception("private memorial"),
        ]

        for error in non_retryable_errors:
            assert strategy.should_retry(error, 0) is False, f"Should not retry: {error}"

    def test_should_retry_retryable_patterns(self):
        """Test should_retry detects retryable error patterns."""
        strategy = RetryStrategy()

        retryable_errors = [
            Exception("timeout occurred"),
            Exception("page crashed"),
            Exception("target crashed"),
            Exception("execution context was destroyed"),
            Exception("protocol error"),
            Exception("session closed"),
            Exception("connection refused"),
            Exception("connection reset"),
            Exception("net::err_connection_closed"),
            Exception("network error"),
            Exception("dns lookup failed"),
        ]

        for error in retryable_errors:
            assert strategy.should_retry(error, 0) is True, f"Should retry: {error}"

    def test_should_retry_unknown_error(self):
        """Test should_retry returns False for unknown errors (safe default)."""
        strategy = RetryStrategy()

        error = Exception("some random error message")

        # Unknown errors should not retry by default (safe behavior)
        assert strategy.should_retry(error, 0) is False

    def test_get_delay_exponential_backoff(self):
        """Test get_delay calculates exponential backoff correctly."""
        config = RetryConfig(base_delay_seconds=2, exponential_base=2, jitter=False)
        strategy = RetryStrategy(config)

        # Retry 0: 2 * (2^0) = 2
        # Retry 1: 2 * (2^1) = 4
        # Retry 2: 2 * (2^2) = 8
        # Retry 3: 2 * (2^3) = 16

        assert strategy.get_delay(0) == 2.0
        assert strategy.get_delay(1) == 4.0
        assert strategy.get_delay(2) == 8.0
        assert strategy.get_delay(3) == 16.0

    def test_get_delay_max_capped(self):
        """Test get_delay respects max_delay cap."""
        config = RetryConfig(
            base_delay_seconds=10, max_delay_seconds=30, jitter=False
        )
        strategy = RetryStrategy(config)

        # Retry 3: 10 * (2^3) = 80, but capped at 30
        delay = strategy.get_delay(3)
        assert delay == 30.0

    def test_get_delay_with_jitter(self):
        """Test get_delay adds jitter when enabled."""
        config = RetryConfig(base_delay_seconds=10, jitter=True)
        strategy = RetryStrategy(config)

        # Jitter factor is random uniform(0.8, 1.2)
        # So delay should be between 8.0 and 12.0
        delay = strategy.get_delay(0)
        assert 8.0 <= delay <= 12.0

    def test_retry_sync_success_first_attempt(self):
        """Test retry_sync succeeds on first attempt."""
        strategy = RetryStrategy()

        call_count = 0

        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = strategy.retry_sync(successful_func)

        assert result == "success"
        assert call_count == 1

    def test_retry_sync_success_after_retries(self):
        """Test retry_sync succeeds after transient failures."""
        strategy = RetryStrategy(RetryConfig(max_retries=3, base_delay_seconds=0))

        call_count = 0

        def eventually_successful_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("transient error")
            return "success"

        result = strategy.retry_sync(eventually_successful_func)

        assert result == "success"
        assert call_count == 3

    def test_retry_sync_non_retryable_error(self):
        """Test retry_sync fails immediately on non-retryable error."""
        strategy = RetryStrategy()

        call_count = 0

        def non_retryable_func():
            nonlocal call_count
            call_count += 1
            raise NonRetryableError("permanent error")

        with pytest.raises(NonRetryableError):
            strategy.retry_sync(non_retryable_func)

        # Should only try once
        assert call_count == 1

    def test_retry_sync_max_retries_exhausted(self):
        """Test retry_sync raises after exhausting max retries."""
        strategy = RetryStrategy(RetryConfig(max_retries=3, base_delay_seconds=0))

        call_count = 0

        def always_failing_func():
            nonlocal call_count
            call_count += 1
            raise RetryableError("always fails")

        with pytest.raises(RetryableError):
            strategy.retry_sync(always_failing_func)

        # Should try initial + 3 retries = 4 total
        assert call_count == 4

    @pytest.mark.asyncio
    async def test_retry_async_success_first_attempt(self):
        """Test retry_async succeeds on first attempt."""
        strategy = RetryStrategy()

        call_count = 0

        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await strategy.retry_async(successful_func)

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_async_success_after_retries(self):
        """Test retry_async succeeds after transient failures."""
        strategy = RetryStrategy(RetryConfig(max_retries=3, base_delay_seconds=0))

        call_count = 0

        async def eventually_successful_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("transient error")
            return "success"

        result = await strategy.retry_async(eventually_successful_func)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_async_non_retryable_error(self):
        """Test retry_async fails immediately on non-retryable error."""
        strategy = RetryStrategy()

        call_count = 0

        async def non_retryable_func():
            nonlocal call_count
            call_count += 1
            raise NonRetryableError("permanent error")

        with pytest.raises(NonRetryableError):
            await strategy.retry_async(non_retryable_func)

        # Should only try once
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_async_max_retries_exhausted(self):
        """Test retry_async raises after exhausting max retries."""
        strategy = RetryStrategy(RetryConfig(max_retries=3, base_delay_seconds=0))

        call_count = 0

        async def always_failing_func():
            nonlocal call_count
            call_count += 1
            raise RetryableError("always fails")

        with pytest.raises(RetryableError):
            await strategy.retry_async(always_failing_func)

        # Should try initial + 3 retries = 4 total
        assert call_count == 4

    @pytest.mark.asyncio
    async def test_retry_async_with_args_and_kwargs(self):
        """Test retry_async passes args and kwargs correctly."""
        strategy = RetryStrategy()

        async def func_with_params(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = await strategy.retry_async(func_with_params, "x", "y", c="z")

        assert result == "x-y-z"

    def test_retry_sync_with_args_and_kwargs(self):
        """Test retry_sync passes args and kwargs correctly."""
        strategy = RetryStrategy()

        def func_with_params(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = strategy.retry_sync(func_with_params, "x", "y", c="z")

        assert result == "x-y-z"

    @pytest.mark.asyncio
    async def test_retry_async_waits_between_attempts(self):
        """Test retry_async waits between retry attempts."""
        strategy = RetryStrategy(RetryConfig(base_delay_seconds=0.1, jitter=False))

        call_times = []

        async def failing_func():
            call_times.append(time.time())
            if len(call_times) < 2:
                raise RetryableError("fail")
            return "success"

        await strategy.retry_async(failing_func)

        # Should have 2 calls with ~0.1s delay between them
        assert len(call_times) == 2
        time_diff = call_times[1] - call_times[0]
        assert time_diff >= 0.1
