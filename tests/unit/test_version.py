"""Tests for version module."""

import re
from datetime import datetime

import pytest

from rmcitecraft.version import (
    VERSION,
    format_version_string,
    get_last_updated,
    get_version_info,
)


class TestVersion:
    """Test version information functions."""

    def test_version_format(self) -> None:
        """Test that VERSION is a valid semver string."""
        # Should match X.Y.Z or X.Y.Z-dev
        assert re.match(r"^\d+\.\d+\.\d+(-dev)?$", VERSION)

    def test_get_version_info(self) -> None:
        """Test get_version_info returns required fields."""
        info = get_version_info()

        assert "version" in info
        assert "last_updated" in info
        assert "status" in info

        assert info["version"] == VERSION
        assert info["status"] in ("development", "release")

        # Verify last_updated is a valid datetime string
        assert len(info["last_updated"]) > 0

    def test_get_last_updated_format(self) -> None:
        """Test get_last_updated returns properly formatted datetime."""
        last_updated = get_last_updated()

        # Should be in format: YYYY-MM-DD HH:MM:SS
        assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", last_updated)

        # Should be parseable as datetime
        datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S")

    def test_format_version_string_with_timestamp(self) -> None:
        """Test format_version_string includes timestamp."""
        version_str = format_version_string(include_timestamp=True)

        assert "RMCitecraft" in version_str
        assert VERSION in version_str
        assert "Last updated:" in version_str

    def test_format_version_string_without_timestamp(self) -> None:
        """Test format_version_string without timestamp."""
        version_str = format_version_string(include_timestamp=False)

        assert "RMCitecraft" in version_str
        assert VERSION in version_str
        assert "Last updated:" not in version_str

    def test_development_status_detection(self) -> None:
        """Test development status detection in version."""
        info = get_version_info()

        if "dev" in VERSION:
            assert info["status"] == "development"
        else:
            assert info["status"] == "release"
