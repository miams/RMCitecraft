"""Entry point for RMCitecraft application.

This module provides the command-line entry point for the application.
Supports daemon mode, process management, and status checking.
"""

import argparse
import atexit
import os
import signal
import sys
import time
from pathlib import Path

from loguru import logger


def get_pid_file() -> Path:
    """Get the PID file path.

    Returns:
        Path to PID file in ~/.rmcitecraft/rmcitecraft.pid
    """
    config_dir = Path.home() / ".rmcitecraft"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "rmcitecraft.pid"


def write_pid_file(pid: int) -> None:
    """Write process ID to PID file.

    Args:
        pid: Process ID to write
    """
    pid_file = get_pid_file()
    pid_file.write_text(str(pid))
    logger.info(f"PID file created: {pid_file}")


def read_pid_file() -> int | None:
    """Read process ID from PID file.

    Returns:
        Process ID or None if file doesn't exist
    """
    pid_file = get_pid_file()
    if not pid_file.exists():
        return None

    try:
        return int(pid_file.read_text().strip())
    except (ValueError, OSError) as e:
        logger.warning(f"Invalid PID file: {e}")
        return None


def remove_pid_file() -> None:
    """Remove PID file."""
    pid_file = get_pid_file()
    if pid_file.exists():
        pid_file.unlink()
        logger.info("PID file removed")


def is_process_running(pid: int) -> bool:
    """Check if a process is running.

    Args:
        pid: Process ID to check

    Returns:
        True if process is running, False otherwise
    """
    try:
        # Send signal 0 to check if process exists
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def daemonize() -> None:
    """Fork the process and run in daemon mode.

    This detaches the process from the terminal and runs it in the background.
    Redirects stdout/stderr to log files.
    """
    # First fork
    try:
        pid = os.fork()
        if pid > 0:
            # Parent process - exit
            sys.exit(0)
    except OSError as e:
        logger.error(f"First fork failed: {e}")
        sys.exit(1)

    # Decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)

    # Second fork
    try:
        pid = os.fork()
        if pid > 0:
            # Parent process - exit
            sys.exit(0)
    except OSError as e:
        logger.error(f"Second fork failed: {e}")
        sys.exit(1)

    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()

    # Open log files for stdout/stderr
    config_dir = Path.home() / ".rmcitecraft"
    config_dir.mkdir(parents=True, exist_ok=True)

    stdout_log = config_dir / "stdout.log"
    stderr_log = config_dir / "stderr.log"

    with open(stdout_log, "a") as out, open(stderr_log, "a") as err:
        os.dup2(out.fileno(), sys.stdout.fileno())
        os.dup2(err.fileno(), sys.stderr.fileno())

    # Write PID file
    write_pid_file(os.getpid())

    # Register cleanup handler
    atexit.register(remove_pid_file)

    # Handle termination signals
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))
    signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(0))


def start_foreground() -> int:
    """Start RMCitecraft in foreground mode.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    # Check if already running
    pid = read_pid_file()
    if pid and is_process_running(pid):
        print(f"❌ RMCitecraft is already running (PID: {pid})")
        print(f"   Use 'rmcitecraft stop' to stop it first")
        return 1

    print("🚀 Starting RMCitecraft in foreground mode...")
    print("   Press Ctrl+C to stop\n")

    # Write PID file for foreground process too
    write_pid_file(os.getpid())
    atexit.register(remove_pid_file)

    # Import and run the main application
    from rmcitecraft.main import main as app_main

    try:
        app_main()
        return 0
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopping RMCitecraft...")
        return 0
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        return 1
    finally:
        remove_pid_file()


def start_daemon() -> int:
    """Start RMCitecraft in daemon mode (background).

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    # Check if already running
    pid = read_pid_file()
    if pid and is_process_running(pid):
        print(f"❌ RMCitecraft is already running (PID: {pid})")
        return 1

    print("🚀 Starting RMCitecraft as daemon...")

    # Fork and daemonize
    daemonize()

    # Import and run the main application (in child process)
    from rmcitecraft.main import main as app_main

    try:
        logger.info("RMCitecraft daemon started")
        app_main()
        return 0
    except Exception as e:
        logger.error(f"Daemon error: {e}", exc_info=True)
        return 1


def stop_application() -> int:
    """Stop the running RMCitecraft daemon.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    pid = read_pid_file()

    if not pid:
        print("❌ RMCitecraft is not running (no PID file found)")
        return 1

    if not is_process_running(pid):
        print(f"❌ RMCitecraft process (PID: {pid}) is not running")
        print("   Cleaning up stale PID file...")
        remove_pid_file()
        return 1

    print(f"⏹️  Stopping RMCitecraft (PID: {pid})...")

    # Send SIGTERM for graceful shutdown
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as e:
        print(f"❌ Failed to stop process: {e}")
        return 1

    # Wait for process to terminate (up to 10 seconds)
    for i in range(100):
        if not is_process_running(pid):
            print("✅ RMCitecraft stopped")
            remove_pid_file()
            return 0
        time.sleep(0.1)

    # If still running after 10 seconds, force kill
    print("   Process did not stop gracefully, forcing...")
    try:
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.5)
        if not is_process_running(pid):
            print("✅ RMCitecraft forcefully stopped")
            remove_pid_file()
            return 0
    except OSError as e:
        print(f"❌ Failed to force stop: {e}")
        return 1

    print("❌ Failed to stop RMCitecraft")
    return 1


def show_status() -> int:
    """Show the status of RMCitecraft.

    Returns:
        Exit code (0 if running, 1 if not running)
    """
    pid = read_pid_file()

    if not pid:
        print("⚫ RMCitecraft is not running")
        return 1

    if is_process_running(pid):
        print(f"✅ RMCitecraft is running (PID: {pid})")

        # Show log file locations
        config_dir = Path.home() / ".rmcitecraft"
        print(f"\n📋 Log files:")
        print(f"   Stdout: {config_dir / 'stdout.log'}")
        print(f"   Stderr: {config_dir / 'stderr.log'}")

        # Show application log
        from rmcitecraft.config import get_config
        config = get_config()
        print(f"   Application: {config.log_file}")

        return 0
    else:
        print(f"❌ RMCitecraft process (PID: {pid}) is not running")
        print("   Cleaning up stale PID file...")
        remove_pid_file()
        return 1


def main() -> int:
    """Main entry point for rmcitecraft command.

    Parses command-line arguments and executes the appropriate command.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = argparse.ArgumentParser(
        prog="rmcitecraft",
        description="RMCitecraft - Automated citation and media management for RootsMagic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  rmcitecraft start           Start in foreground (press Ctrl+C to stop)
  rmcitecraft start -d        Start as background daemon
  rmcitecraft stop            Stop the daemon
  rmcitecraft status          Check if running

For more information, see: https://github.com/yourusername/rmcitecraft
        """,
    )

    # Add subcommands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start RMCitecraft")
    start_parser.add_argument(
        "-d",
        "--daemon",
        action="store_true",
        help="Run as background daemon",
    )

    # Stop command
    subparsers.add_parser("stop", help="Stop RMCitecraft daemon")

    # Status command
    subparsers.add_parser("status", help="Show RMCitecraft status")

    # Parse arguments
    args = parser.parse_args()

    # Execute command
    if args.command == "start":
        if args.daemon:
            return start_daemon()
        else:
            return start_foreground()
    elif args.command == "stop":
        return stop_application()
    elif args.command == "status":
        return show_status()
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
