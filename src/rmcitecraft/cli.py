"""Command-line interface for RMCitecraft.

This module provides the CLI commands for starting, stopping, and managing
the RMCitecraft application.
"""

import sys
from typing import Optional

from loguru import logger

from rmcitecraft.daemon import get_status, is_running, start_daemon, stop_daemon
from rmcitecraft.version import format_version_string, get_version_info

__all__ = ["cli_main"]


def print_version() -> None:
    """Print version information."""
    print(format_version_string(include_timestamp=True))


def print_status() -> None:
    """Print application status."""
    print_version()
    print()

    status = get_status()

    if status["running"]:
        print(f"Status: ✓ Running (PID: {status['pid']})")
    else:
        print("Status: ✗ Not running")

    print(f"Database: {status['database_path']}")

    # Show config path if available
    if status["config_path"] != "N/A":
        print(f"Config: {status['config_path']}")


def cmd_start(background: bool = False) -> int:
    """Start the application.

    Args:
        background: If True, start in background mode

    Returns:
        Exit code (0 for success, 1 for error)
    """
    print_version()
    print()

    if is_running():
        print("✗ RMCitecraft is already running")
        print()
        print_status()
        return 1

    if background:
        print("Starting RMCitecraft in background mode...")
        success = start_daemon(background=True)

        if success:
            print("✓ RMCitecraft started successfully")
            print()
            print_status()
            return 0
        else:
            print("✗ Failed to start RMCitecraft")
            return 1
    else:
        # Start in foreground mode
        print("Starting RMCitecraft...")
        print("(Use Ctrl+C to stop)")
        print()

        try:
            # Import and run the main app
            from rmcitecraft.main import main as run_app

            # Write PID file for foreground process
            import os
            from rmcitecraft.daemon import write_pid_file, remove_pid_file

            write_pid_file(os.getpid())

            try:
                run_app()
                return 0
            finally:
                # Clean up PID file on exit
                remove_pid_file()

        except KeyboardInterrupt:
            print("\n✓ RMCitecraft stopped")
            return 0
        except Exception as e:
            print(f"\n✗ Error: {e}")
            logger.exception("Application error")
            return 1


def cmd_stop() -> int:
    """Stop the application.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    print_version()
    print()

    if not is_running():
        print("✗ RMCitecraft is not running")
        return 1

    print("Stopping RMCitecraft...")
    success = stop_daemon()

    if success:
        print("✓ RMCitecraft stopped successfully")
        return 0
    else:
        print("✗ Failed to stop RMCitecraft")
        return 1


def cmd_status() -> int:
    """Show application status.

    Returns:
        Exit code (0 if running, 1 if not running)
    """
    print_status()
    return 0 if is_running() else 1


def cmd_restart() -> int:
    """Restart the application.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    print_version()
    print()

    # Stop if running
    if is_running():
        print("Stopping RMCitecraft...")
        stop_daemon()
        import time
        time.sleep(1)  # Wait a moment

    # Start in background mode
    print("Starting RMCitecraft...")
    return cmd_start(background=True)


def cmd_serve() -> int:
    """Start the application server (internal command for daemon mode).

    This is called by the daemon process and should not be called directly
    by users.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        from rmcitecraft.main import main as run_app
        run_app()
        return 0
    except Exception as e:
        logger.exception("Server error")
        print(f"✗ Server error: {e}", file=sys.stderr)
        return 1


def print_help() -> None:
    """Print CLI help message."""
    print_version()
    print()
    print("Usage: rmcitecraft [COMMAND]")
    print()
    print("Commands:")
    print("  start       Start RMCitecraft in foreground mode")
    print("  start -d    Start RMCitecraft in background (daemon) mode")
    print("  stop        Stop the running RMCitecraft instance")
    print("  restart     Restart RMCitecraft (stop + start in background)")
    print("  status      Show current status and version information")
    print("  version     Show version information")
    print("  help        Show this help message")
    print()
    print("Examples:")
    print("  rmcitecraft start           # Start in foreground")
    print("  rmcitecraft start -d        # Start in background")
    print("  rmcitecraft status          # Check if running")
    print("  rmcitecraft stop            # Stop the application")
    print()


def cli_main(args: Optional[list[str]] = None) -> int:
    """Main CLI entry point.

    Args:
        args: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    if args is None:
        args = sys.argv[1:]

    # No command or help
    if not args or args[0] in ("help", "-h", "--help"):
        print_help()
        return 0

    command = args[0].lower()

    # Parse flags
    flags = args[1:] if len(args) > 1 else []
    background = "-d" in flags or "--daemon" in flags

    # Execute command
    if command == "start":
        return cmd_start(background=background)
    elif command == "stop":
        return cmd_stop()
    elif command == "status":
        return cmd_status()
    elif command == "restart":
        return cmd_restart()
    elif command == "version":
        print_version()
        return 0
    elif command == "serve":
        # Internal command for daemon mode
        return cmd_serve()
    else:
        print(f"✗ Unknown command: {command}")
        print()
        print_help()
        return 1
