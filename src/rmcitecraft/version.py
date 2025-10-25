"""Version information for RMCitecraft.

This module provides version and build information for the application.
"""

import importlib.metadata
from datetime import datetime
from pathlib import Path
from typing import Optional

__all__ = ["VERSION", "get_version_info", "get_last_updated"]

# Version from pyproject.toml
try:
    VERSION = importlib.metadata.version("rmcitecraft")
except importlib.metadata.PackageNotFoundError:
    VERSION = "0.1.0-dev"


def get_version_info() -> dict[str, str]:
    """Get version information including last updated time.

    Returns:
        Dictionary with version, build time, and status information
    """
    return {
        "version": VERSION,
        "last_updated": get_last_updated(),
        "status": "development" if "dev" in VERSION else "release",
    }


def get_last_updated() -> str:
    """Get the last modification time of the codebase.

    This checks the most recently modified Python file in the src directory
    to determine when the code was last changed.

    Returns:
        ISO 8601 formatted datetime string of last update
    """
    try:
        # Get the source directory
        src_dir = Path(__file__).parent

        # Find all Python files
        py_files = list(src_dir.rglob("*.py"))

        if not py_files:
            return datetime.now().isoformat()

        # Get the most recent modification time
        latest_mtime = max(f.stat().st_mtime for f in py_files)
        latest_time = datetime.fromtimestamp(latest_mtime)

        return latest_time.strftime("%Y-%m-%d %H:%M:%S")

    except Exception:
        # Fallback to current time if there's any error
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_version_string(include_timestamp: bool = True) -> str:
    """Format version information as a human-readable string.

    Args:
        include_timestamp: Whether to include the last updated timestamp

    Returns:
        Formatted version string
    """
    info = get_version_info()
    version_str = f"RMCitecraft v{info['version']}"

    if info["status"] == "development":
        version_str += " (development)"

    if include_timestamp:
        version_str += f"\nLast updated: {info['last_updated']}"

    return version_str
