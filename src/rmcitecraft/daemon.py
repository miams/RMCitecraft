"""Daemon management for RMCitecraft.

This module handles process management, PID file operations, and status tracking.
"""

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

from rmcitecraft.config import get_config

__all__ = ["is_running", "get_pid", "start_daemon", "stop_daemon", "get_status"]


def get_pid_file() -> Path:
    """Get the path to the PID file.

    Returns:
        Path to PID file in user's home directory
    """
    # Store PID file in user's home directory
    pid_dir = Path.home() / ".rmcitecraft"
    pid_dir.mkdir(exist_ok=True)
    return pid_dir / "rmcitecraft.pid"


def get_pid() -> Optional[int]:
    """Get the PID of the running application from PID file.

    Returns:
        PID of running process, or None if not running
    """
    pid_file = get_pid_file()

    if not pid_file.exists():
        return None

    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())

        # Verify the process is actually running
        if is_process_running(pid):
            return pid
        else:
            # Stale PID file, remove it
            pid_file.unlink(missing_ok=True)
            return None

    except (ValueError, OSError) as e:
        logger.warning(f"Error reading PID file: {e}")
        return None


def write_pid_file(pid: int) -> None:
    """Write PID to PID file.

    Args:
        pid: Process ID to write
    """
    pid_file = get_pid_file()

    try:
        with open(pid_file, "w") as f:
            f.write(str(pid))
        logger.debug(f"Wrote PID {pid} to {pid_file}")
    except OSError as e:
        logger.error(f"Failed to write PID file: {e}")


def remove_pid_file() -> None:
    """Remove the PID file."""
    pid_file = get_pid_file()
    pid_file.unlink(missing_ok=True)
    logger.debug(f"Removed PID file: {pid_file}")


def is_process_running(pid: int) -> bool:
    """Check if a process with given PID is running.

    Args:
        pid: Process ID to check

    Returns:
        True if process is running, False otherwise
    """
    try:
        # Send signal 0 to check if process exists
        # This doesn't actually send a signal, just checks permissions
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def is_running() -> bool:
    """Check if RMCitecraft is currently running.

    Returns:
        True if application is running, False otherwise
    """
    pid = get_pid()
    return pid is not None


def start_daemon(background: bool = False) -> bool:
    """Start the RMCitecraft application.

    Args:
        background: If True, start in background mode (daemon)

    Returns:
        True if started successfully, False if already running
    """
    if is_running():
        logger.warning("RMCitecraft is already running")
        return False

    try:
        if background:
            # Start in background mode
            # Use subprocess to launch a detached process
            python_exec = sys.executable
            module_args = [python_exec, "-m", "rmcitecraft", "serve"]

            # Start detached process
            process = subprocess.Popen(
                module_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,  # Detach from parent
            )

            # Write PID file
            write_pid_file(process.pid)

            logger.info(f"Started RMCitecraft in background (PID: {process.pid})")
            return True
        else:
            # Start in foreground mode (will be handled by caller)
            logger.info("Starting RMCitecraft in foreground mode")
            return True

    except Exception as e:
        logger.error(f"Failed to start RMCitecraft: {e}")
        return False


def stop_daemon() -> bool:
    """Stop the running RMCitecraft application.

    Returns:
        True if stopped successfully, False if not running
    """
    pid = get_pid()

    if pid is None:
        logger.warning("RMCitecraft is not running")
        return False

    try:
        # Send SIGTERM to gracefully shut down
        logger.info(f"Stopping RMCitecraft (PID: {pid})")
        os.kill(pid, signal.SIGTERM)

        # Wait a moment for graceful shutdown
        import time
        for _ in range(10):  # Wait up to 5 seconds
            time.sleep(0.5)
            if not is_process_running(pid):
                break

        # If still running, force kill
        if is_process_running(pid):
            logger.warning(f"Process {pid} did not stop gracefully, forcing...")
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)

        # Remove PID file
        remove_pid_file()

        logger.info("RMCitecraft stopped successfully")
        return True

    except OSError as e:
        logger.error(f"Failed to stop RMCitecraft: {e}")
        remove_pid_file()  # Clean up PID file anyway
        return False


def get_status() -> dict[str, any]:
    """Get the current status of RMCitecraft.

    Returns:
        Dictionary with status information:
        - running: bool
        - pid: Optional[int]
        - config_path: str
        - database_path: str
    """
    config = get_config()
    pid = get_pid()

    return {
        "running": pid is not None,
        "pid": pid,
        "config_path": str(config.config_file) if hasattr(config, "config_file") else "N/A",
        "database_path": str(config.rm_database_path),
    }
