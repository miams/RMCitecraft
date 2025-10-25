"""Tests for daemon management module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rmcitecraft.daemon import (
    get_pid,
    get_pid_file,
    is_process_running,
    is_running,
    remove_pid_file,
    write_pid_file,
)


class TestPIDFile:
    """Test PID file operations."""

    def test_get_pid_file_path(self) -> None:
        """Test get_pid_file returns correct path."""
        pid_file = get_pid_file()

        assert pid_file.name == "rmcitecraft.pid"
        assert ".rmcitecraft" in str(pid_file)

    def test_write_and_read_pid_file(self, tmp_path: Path) -> None:
        """Test writing and reading PID file."""
        test_pid = 12345

        # Mock get_pid_file to use tmp_path
        with patch("rmcitecraft.daemon.get_pid_file") as mock_get_pid_file:
            pid_file = tmp_path / "test.pid"
            mock_get_pid_file.return_value = pid_file

            # Write PID
            write_pid_file(test_pid)

            # Verify file exists and contains correct PID
            assert pid_file.exists()
            assert pid_file.read_text().strip() == str(test_pid)

    def test_remove_pid_file(self, tmp_path: Path) -> None:
        """Test removing PID file."""
        with patch("rmcitecraft.daemon.get_pid_file") as mock_get_pid_file:
            pid_file = tmp_path / "test.pid"
            mock_get_pid_file.return_value = pid_file

            # Create PID file
            pid_file.write_text("12345")
            assert pid_file.exists()

            # Remove it
            remove_pid_file()
            assert not pid_file.exists()

    def test_get_pid_no_file(self, tmp_path: Path) -> None:
        """Test get_pid when no PID file exists."""
        with patch("rmcitecraft.daemon.get_pid_file") as mock_get_pid_file:
            pid_file = tmp_path / "nonexistent.pid"
            mock_get_pid_file.return_value = pid_file

            pid = get_pid()
            assert pid is None

    def test_get_pid_with_running_process(self, tmp_path: Path) -> None:
        """Test get_pid with a running process."""
        current_pid = os.getpid()

        with patch("rmcitecraft.daemon.get_pid_file") as mock_get_pid_file:
            pid_file = tmp_path / "test.pid"
            mock_get_pid_file.return_value = pid_file

            # Write current process PID (which is running)
            pid_file.write_text(str(current_pid))

            pid = get_pid()
            assert pid == current_pid

    def test_get_pid_with_stale_process(self, tmp_path: Path) -> None:
        """Test get_pid removes stale PID file."""
        fake_pid = 999999  # Unlikely to be a real process

        with patch("rmcitecraft.daemon.get_pid_file") as mock_get_pid_file:
            pid_file = tmp_path / "test.pid"
            mock_get_pid_file.return_value = pid_file

            # Write fake PID
            pid_file.write_text(str(fake_pid))

            # Should return None and remove file
            pid = get_pid()
            assert pid is None
            assert not pid_file.exists()


class TestProcessChecking:
    """Test process checking functions."""

    def test_is_process_running_current_process(self) -> None:
        """Test is_process_running for current process."""
        current_pid = os.getpid()
        assert is_process_running(current_pid) is True

    def test_is_process_running_nonexistent_process(self) -> None:
        """Test is_process_running for nonexistent process."""
        fake_pid = 999999
        assert is_process_running(fake_pid) is False

    def test_is_running_with_running_process(self, tmp_path: Path) -> None:
        """Test is_running when application is running."""
        current_pid = os.getpid()

        with patch("rmcitecraft.daemon.get_pid_file") as mock_get_pid_file:
            pid_file = tmp_path / "test.pid"
            mock_get_pid_file.return_value = pid_file

            # Write current PID
            pid_file.write_text(str(current_pid))

            assert is_running() is True

    def test_is_running_without_pid_file(self, tmp_path: Path) -> None:
        """Test is_running when no PID file exists."""
        with patch("rmcitecraft.daemon.get_pid_file") as mock_get_pid_file:
            pid_file = tmp_path / "nonexistent.pid"
            mock_get_pid_file.return_value = pid_file

            assert is_running() is False


class TestGetStatus:
    """Test get_status function."""

    def test_get_status_structure(self) -> None:
        """Test get_status returns correct structure."""
        from rmcitecraft.daemon import get_status

        status = get_status()

        assert "running" in status
        assert "pid" in status
        assert "config_path" in status
        assert "database_path" in status

        assert isinstance(status["running"], bool)
        assert status["pid"] is None or isinstance(status["pid"], int)

    def test_get_status_when_running(self, tmp_path: Path) -> None:
        """Test get_status when application is running."""
        current_pid = os.getpid()

        with patch("rmcitecraft.daemon.get_pid_file") as mock_get_pid_file:
            pid_file = tmp_path / "test.pid"
            mock_get_pid_file.return_value = pid_file

            # Write current PID
            pid_file.write_text(str(current_pid))

            from rmcitecraft.daemon import get_status

            status = get_status()

            assert status["running"] is True
            assert status["pid"] == current_pid

    def test_get_status_when_not_running(self, tmp_path: Path) -> None:
        """Test get_status when application is not running."""
        with patch("rmcitecraft.daemon.get_pid_file") as mock_get_pid_file:
            pid_file = tmp_path / "nonexistent.pid"
            mock_get_pid_file.return_value = pid_file

            from rmcitecraft.daemon import get_status

            status = get_status()

            assert status["running"] is False
            assert status["pid"] is None
