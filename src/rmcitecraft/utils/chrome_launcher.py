"""
Chrome Browser Launcher for Playwright Automation

Helps launch Chrome with remote debugging enabled so Playwright can connect.
"""

import subprocess
from pathlib import Path

from loguru import logger


def get_chrome_path() -> Path:
    """Get path to Chrome application on macOS."""
    chrome_path = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

    if not chrome_path.exists():
        raise FileNotFoundError(
            "Google Chrome not found at expected location. "
            "Please install Chrome or update the path."
        )

    return chrome_path


def is_chrome_running_with_debugging() -> bool:
    """
    Check if Chrome is already running with remote debugging enabled.

    Returns:
        True if Chrome is running with debugging port 9222
    """
    try:
        # Check for Chrome process with remote debugging flag
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            check=False,
        )
        # Look for Chrome process with --remote-debugging-port=9222
        for line in result.stdout.split("\n"):
            if "chrome" in line.lower() and "--remote-debugging-port=9222" in line.lower():
                return True
        return False
    except Exception as e:
        logger.warning(f"Failed to check Chrome debugging status: {e}")
        return False


def launch_chrome_with_debugging() -> subprocess.Popen | None:
    """
    Launch Chrome with remote debugging enabled.

    Returns:
        Popen process or None if launch failed
    """
    try:
        chrome_path = get_chrome_path()
        # Use separate profile directory for debugging (Chrome requirement)
        user_data_dir = Path.home() / "Library/Application Support/Google/Chrome-RMCitecraft"

        # Check if already running
        if is_chrome_running_with_debugging():
            logger.info("Chrome is already running with remote debugging on port 9222")
            return None

        logger.info("Launching Chrome with remote debugging on port 9222...")
        logger.info(f"Using debug profile: {user_data_dir}")

        # Launch Chrome with remote debugging
        process = subprocess.Popen(
            [
                str(chrome_path),
                "--remote-debugging-port=9222",
                f"--user-data-dir={user_data_dir}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        logger.info(f"Chrome launched with PID {process.pid}")
        return process

    except FileNotFoundError as e:
        logger.error(f"Chrome not found: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to launch Chrome: {e}", exc_info=True)
        return None


def get_launch_instructions() -> str:
    """
    Get instructions for manually launching Chrome with debugging.

    Returns:
        Command string to run in terminal
    """
    chrome_path = get_chrome_path()
    # Use separate profile for debugging (Chrome requirement - cannot use default profile)
    user_data_dir = Path.home() / "Library/Application Support/Google/Chrome-RMCitecraft"

    return f"""
To manually launch Chrome with remote debugging:

1. Close all Chrome windows
2. Run this command in Terminal:

    "{chrome_path}" \\
        --remote-debugging-port=9222 \\
        --user-data-dir="{user_data_dir}"

3. Chrome will open with debugging enabled (uses separate profile)
4. Log into FamilySearch in this Chrome window
5. Click "Connect to Chrome" in RMCitecraft

Note: This uses a separate Chrome profile (Chrome-RMCitecraft) because
Chrome requires a non-default profile directory for remote debugging.
"""
