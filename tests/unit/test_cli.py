"""Tests for CLI module."""

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rmcitecraft.cli import cli_main


class TestCLICommands:
    """Test CLI command parsing and execution."""

    def test_cli_help(self, capsys: pytest.CaptureFixture) -> None:
        """Test help command."""
        exit_code = cli_main(["help"])

        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Usage: rmcitecraft" in captured.out
        assert "Commands:" in captured.out
        assert "start" in captured.out
        assert "stop" in captured.out
        assert "status" in captured.out

    def test_cli_no_args(self, capsys: pytest.CaptureFixture) -> None:
        """Test CLI with no arguments shows help."""
        exit_code = cli_main([])

        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Usage: rmcitecraft" in captured.out

    def test_cli_version(self, capsys: pytest.CaptureFixture) -> None:
        """Test version command."""
        exit_code = cli_main(["version"])

        assert exit_code == 0

        captured = capsys.readouterr()
        assert "RMCitecraft" in captured.out
        assert "v0.1.0" in captured.out
        assert "Last updated:" in captured.out

    def test_cli_unknown_command(self, capsys: pytest.CaptureFixture) -> None:
        """Test unknown command shows error."""
        exit_code = cli_main(["invalid_command"])

        assert exit_code == 1

        captured = capsys.readouterr()
        assert "Unknown command" in captured.out

    @patch("rmcitecraft.cli.is_running")
    def test_cli_status_not_running(
        self, mock_is_running: MagicMock, capsys: pytest.CaptureFixture
    ) -> None:
        """Test status command when not running."""
        mock_is_running.return_value = False

        with patch("rmcitecraft.cli.get_status") as mock_get_status:
            mock_get_status.return_value = {
                "running": False,
                "pid": None,
                "config_path": "N/A",
                "database_path": "data/Iiams.rmtree",
            }

            exit_code = cli_main(["status"])

            # Status command returns 1 when not running
            assert exit_code == 1

            captured = capsys.readouterr()
            assert "Not running" in captured.out

    @patch("rmcitecraft.cli.is_running")
    def test_cli_status_running(
        self, mock_is_running: MagicMock, capsys: pytest.CaptureFixture
    ) -> None:
        """Test status command when running."""
        mock_is_running.return_value = True

        with patch("rmcitecraft.cli.get_status") as mock_get_status:
            mock_get_status.return_value = {
                "running": True,
                "pid": 12345,
                "config_path": "/path/to/config",
                "database_path": "data/Iiams.rmtree",
            }

            exit_code = cli_main(["status"])

            # Status command returns 0 when running
            assert exit_code == 0

            captured = capsys.readouterr()
            assert "Running" in captured.out
            assert "12345" in captured.out


class TestStartCommand:
    """Test start command."""

    @patch("rmcitecraft.cli.is_running")
    def test_start_when_already_running(
        self, mock_is_running: MagicMock, capsys: pytest.CaptureFixture
    ) -> None:
        """Test start command when already running."""
        mock_is_running.return_value = True

        with patch("rmcitecraft.cli.get_status") as mock_get_status:
            mock_get_status.return_value = {
                "running": True,
                "pid": 12345,
                "config_path": "N/A",
                "database_path": "data/Iiams.rmtree",
            }

            exit_code = cli_main(["start"])

            assert exit_code == 1

            captured = capsys.readouterr()
            assert "already running" in captured.out

    @patch("rmcitecraft.cli.is_running")
    @patch("rmcitecraft.cli.start_daemon")
    def test_start_background_success(
        self,
        mock_start_daemon: MagicMock,
        mock_is_running: MagicMock,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Test start command in background mode."""
        mock_is_running.return_value = False
        mock_start_daemon.return_value = True

        with patch("rmcitecraft.cli.get_status") as mock_get_status:
            mock_get_status.return_value = {
                "running": False,
                "pid": None,
                "config_path": "N/A",
                "database_path": "data/Iiams.rmtree",
            }

            exit_code = cli_main(["start", "-d"])

            assert exit_code == 0
            mock_start_daemon.assert_called_once_with(background=True)

            captured = capsys.readouterr()
            assert "started successfully" in captured.out

    @patch("rmcitecraft.cli.is_running")
    @patch("rmcitecraft.cli.start_daemon")
    def test_start_background_failure(
        self,
        mock_start_daemon: MagicMock,
        mock_is_running: MagicMock,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Test start command failure in background mode."""
        mock_is_running.return_value = False
        mock_start_daemon.return_value = False

        exit_code = cli_main(["start", "-d"])

        assert exit_code == 1

        captured = capsys.readouterr()
        assert "Failed to start" in captured.out


class TestStopCommand:
    """Test stop command."""

    @patch("rmcitecraft.cli.is_running")
    def test_stop_when_not_running(
        self, mock_is_running: MagicMock, capsys: pytest.CaptureFixture
    ) -> None:
        """Test stop command when not running."""
        mock_is_running.return_value = False

        exit_code = cli_main(["stop"])

        assert exit_code == 1

        captured = capsys.readouterr()
        assert "not running" in captured.out

    @patch("rmcitecraft.cli.is_running")
    @patch("rmcitecraft.cli.stop_daemon")
    def test_stop_success(
        self,
        mock_stop_daemon: MagicMock,
        mock_is_running: MagicMock,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Test successful stop command."""
        mock_is_running.return_value = True
        mock_stop_daemon.return_value = True

        exit_code = cli_main(["stop"])

        assert exit_code == 0
        mock_stop_daemon.assert_called_once()

        captured = capsys.readouterr()
        assert "stopped successfully" in captured.out

    @patch("rmcitecraft.cli.is_running")
    @patch("rmcitecraft.cli.stop_daemon")
    def test_stop_failure(
        self,
        mock_stop_daemon: MagicMock,
        mock_is_running: MagicMock,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Test failed stop command."""
        mock_is_running.return_value = True
        mock_stop_daemon.return_value = False

        exit_code = cli_main(["stop"])

        assert exit_code == 1

        captured = capsys.readouterr()
        assert "Failed to stop" in captured.out


class TestRestartCommand:
    """Test restart command."""

    @patch("rmcitecraft.cli.is_running")
    @patch("rmcitecraft.cli.stop_daemon")
    @patch("rmcitecraft.cli.start_daemon")
    def test_restart_when_running(
        self,
        mock_start_daemon: MagicMock,
        mock_stop_daemon: MagicMock,
        mock_is_running: MagicMock,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Test restart command when application is running."""
        # First call: check if running before restart (True)
        # Second call: check if running before start (False)
        mock_is_running.side_effect = [True, False]
        mock_stop_daemon.return_value = True
        mock_start_daemon.return_value = True

        with patch("rmcitecraft.cli.get_status") as mock_get_status:
            mock_get_status.return_value = {
                "running": False,
                "pid": None,
                "config_path": "N/A",
                "database_path": "data/Iiams.rmtree",
            }

            exit_code = cli_main(["restart"])

            assert exit_code == 0
            mock_stop_daemon.assert_called_once()
            # Start is called by cmd_start which is called by cmd_restart

            captured = capsys.readouterr()
            assert "Stopping" in captured.out or "Starting" in captured.out
