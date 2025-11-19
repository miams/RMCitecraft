"""
Page health monitoring and crash recovery for Playwright browser automation.

Detects crashed or unresponsive pages and attempts recovery to enable
robust batch processing.
"""

import asyncio
from typing import Any

from loguru import logger
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError


class PageHealthStatus:
    """Page health check result."""

    def __init__(self, is_healthy: bool, error: str | None = None):
        """Initialize health status.

        Args:
            is_healthy: Whether page is responsive
            error: Error message if unhealthy
        """
        self.is_healthy = is_healthy
        self.error = error

    def __bool__(self) -> bool:
        """Allow boolean evaluation."""
        return self.is_healthy

    def __str__(self) -> str:
        """String representation."""
        if self.is_healthy:
            return "Healthy"
        return f"Unhealthy: {self.error}"


class PageHealthMonitor:
    """Monitor browser page health and recover from crashes."""

    def __init__(self, health_check_timeout_ms: int = 2000):
        """Initialize monitor.

        Args:
            health_check_timeout_ms: Timeout for health checks in milliseconds
        """
        self.health_check_timeout_ms = health_check_timeout_ms
        self.last_health_check: PageHealthStatus | None = None

    async def check_page_health(self, page: Page) -> PageHealthStatus:
        """Test if page is responsive.

        Args:
            page: Playwright page to check

        Returns:
            PageHealthStatus indicating if page is healthy
        """
        try:
            # Try simple JavaScript evaluation to test if page context is alive
            result = await asyncio.wait_for(
                page.evaluate("() => 1 + 1"),
                timeout=self.health_check_timeout_ms / 1000
            )

            if result == 2:
                status = PageHealthStatus(is_healthy=True)
                logger.debug("Page health check passed")
            else:
                status = PageHealthStatus(
                    is_healthy=False,
                    error="Unexpected evaluation result"
                )
                logger.warning("Page health check failed: unexpected result")

        except asyncio.TimeoutError:
            status = PageHealthStatus(
                is_healthy=False,
                error="Health check timeout - page unresponsive"
            )
            logger.warning(
                f"Page health check timeout after {self.health_check_timeout_ms}ms"
            )

        except PlaywrightTimeoutError:
            status = PageHealthStatus(
                is_healthy=False,
                error="Playwright timeout - page unresponsive"
            )
            logger.warning("Page health check failed: Playwright timeout")

        except Exception as e:
            error_msg = str(e)

            # Check for common crash indicators
            if any(indicator in error_msg.lower() for indicator in [
                "target crashed",
                "page crashed",
                "execution context was destroyed",
                "protocol error",
                "session closed",
            ]):
                status = PageHealthStatus(
                    is_healthy=False,
                    error=f"Page crashed: {error_msg}"
                )
                logger.error(f"Page health check failed: Page crashed - {error_msg}")
            else:
                status = PageHealthStatus(
                    is_healthy=False,
                    error=f"Health check error: {error_msg}"
                )
                logger.warning(f"Page health check failed: {error_msg}")

        self.last_health_check = status
        return status

    async def wait_for_page_ready(
        self,
        page: Page,
        timeout_ms: int = 30000,
        wait_for_selector: str | None = None,
    ) -> bool:
        """Wait for page to be fully loaded and ready.

        Args:
            page: Playwright page
            timeout_ms: Maximum wait time in milliseconds
            wait_for_selector: Optional CSS selector to wait for

        Returns:
            True if page is ready, False if timeout
        """
        try:
            # Wait for DOM content to load
            await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)

            # Optionally wait for specific selector
            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=timeout_ms)

            logger.debug("Page ready")
            return True

        except PlaywrightTimeoutError:
            logger.warning(f"Page ready timeout after {timeout_ms}ms")
            return False

        except Exception as e:
            logger.error(f"Error waiting for page ready: {e}")
            return False

    def is_crash_error(self, error: Exception) -> bool:
        """Check if error indicates a page/browser crash.

        Args:
            error: Exception to check

        Returns:
            True if error is a crash indicator
        """
        error_msg = str(error).lower()

        crash_indicators = [
            "target crashed",
            "page crashed",
            "execution context was destroyed",
            "protocol error",
            "session closed",
            "connection closed",
            "browser has been closed",
        ]

        return any(indicator in error_msg for indicator in crash_indicators)

    def is_network_error(self, error: Exception) -> bool:
        """Check if error indicates a network issue.

        Args:
            error: Exception to check

        Returns:
            True if error is a network indicator
        """
        error_msg = str(error).lower()

        network_indicators = [
            "net::err_",
            "timeout",
            "connection refused",
            "connection reset",
            "network error",
            "dns",
        ]

        return any(indicator in error_msg for indicator in network_indicators)

    def is_retryable_error(self, error: Exception) -> bool:
        """Check if error is potentially retryable.

        Args:
            error: Exception to check

        Returns:
            True if error might succeed on retry
        """
        return self.is_network_error(error) or self.is_crash_error(error)

    async def diagnose_page_issue(self, page: Page, error: Exception) -> dict[str, Any]:
        """Diagnose page issues after an error.

        Args:
            page: Playwright page
            error: Exception that occurred

        Returns:
            Dict with diagnostic information
        """
        diagnosis = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "is_crash": self.is_crash_error(error),
            "is_network": self.is_network_error(error),
            "is_retryable": self.is_retryable_error(error),
        }

        # Try to get page health
        try:
            health = await self.check_page_health(page)
            diagnosis["page_healthy"] = health.is_healthy
            diagnosis["health_error"] = health.error
        except Exception as e:
            diagnosis["page_healthy"] = False
            diagnosis["health_error"] = f"Failed to check health: {e}"

        # Try to get page URL
        try:
            diagnosis["current_url"] = page.url
        except Exception:
            diagnosis["current_url"] = "unknown"

        logger.info(f"Page diagnosis: {diagnosis}")
        return diagnosis


class PageRecoveryManager:
    """Manage page crash recovery strategies."""

    def __init__(self, health_monitor: PageHealthMonitor):
        """Initialize recovery manager.

        Args:
            health_monitor: Page health monitor instance
        """
        self.health_monitor = health_monitor
        self.recovery_attempts = 0
        self.max_recovery_attempts = 3

    async def attempt_recovery(self, page: Page, automation_service: Any) -> Page | None:
        """Attempt to recover crashed page.

        Args:
            page: Crashed page
            automation_service: FindAGraveAutomationService instance

        Returns:
            Recovered page or None if recovery failed
        """
        if self.recovery_attempts >= self.max_recovery_attempts:
            logger.error(
                f"Max recovery attempts ({self.max_recovery_attempts}) exceeded"
            )
            return None

        self.recovery_attempts += 1
        logger.info(
            f"Attempting page recovery (attempt {self.recovery_attempts}/"
            f"{self.max_recovery_attempts})"
        )

        try:
            # Check if browser connection is still alive
            try:
                await automation_service.browser.version()
                logger.debug("Browser connection is alive")
            except Exception:
                logger.error("Browser connection lost - cannot recover")
                return None

            # Try to get a fresh page
            context = automation_service.browser.contexts[0]
            pages = context.pages

            if pages:
                # Use existing page
                new_page = pages[0]
                logger.info("Reusing existing browser page")
            else:
                # Create new page
                new_page = await context.new_page()
                logger.info("Created new browser page")

            # Health check the new page
            health = await self.health_monitor.check_page_health(new_page)

            if health.is_healthy:
                logger.info("Page recovery successful")
                self.recovery_attempts = 0  # Reset counter on success
                return new_page
            else:
                logger.error(f"Recovered page is unhealthy: {health.error}")
                return None

        except Exception as e:
            logger.error(f"Page recovery failed: {e}")
            return None

    def reset_recovery_counter(self) -> None:
        """Reset recovery attempt counter after successful processing."""
        self.recovery_attempts = 0
