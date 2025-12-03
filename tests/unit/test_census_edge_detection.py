"""Unit tests for census edge detection."""

import pytest

from rmcitecraft.services.census_edge_detection import (
    EdgeDetectionResult,
    detect_edge_conditions,
    get_max_line_for_year,
    is_edge_line,
)


class TestDetectEdgeConditions:
    """Tests for detect_edge_conditions function."""

    def test_line_1_head_warning(self):
        """Line 1 with Head relationship still gets warning."""
        result = detect_edge_conditions(
            line_number=1,
            census_year=1950,
            relationship_to_head="Head",
        )
        assert result.first_line_warning is True
        assert result.last_line_warning is False
        assert "previous page" in result.warning_message

    def test_line_1_wife_warning(self):
        """Line 1 with non-head gets stronger warning."""
        result = detect_edge_conditions(
            line_number=1,
            census_year=1950,
            relationship_to_head="Wife",
        )
        assert result.first_line_warning is True
        assert "Wife" in result.warning_message
        assert "previous page" in result.warning_message

    def test_last_line_1950_warning(self):
        """Line 30 (last line for 1950) gets warning."""
        result = detect_edge_conditions(
            line_number=30,
            census_year=1950,
            relationship_to_head="Head",
        )
        assert result.first_line_warning is False
        assert result.last_line_warning is True
        assert "30/30" in result.warning_message
        assert "next page" in result.warning_message

    def test_near_last_line_1950_warning(self):
        """Line 28-29 (within 2 of last for 1950) gets warning."""
        result = detect_edge_conditions(
            line_number=28,
            census_year=1950,
            relationship_to_head="Son",
        )
        assert result.last_line_warning is True
        assert "28/30" in result.warning_message

    def test_last_line_1940_warning(self):
        """Line 40 (last line for 1940) gets warning."""
        result = detect_edge_conditions(
            line_number=40,
            census_year=1940,
            relationship_to_head="Daughter",
        )
        assert result.last_line_warning is True
        assert "40/40" in result.warning_message

    def test_middle_line_no_warning(self):
        """Middle lines should not trigger warnings."""
        result = detect_edge_conditions(
            line_number=15,
            census_year=1950,
            relationship_to_head="Head",
        )
        assert result.first_line_warning is False
        assert result.last_line_warning is False
        assert result.warning_message == ""

    def test_none_line_number(self):
        """None line number should not trigger warnings."""
        result = detect_edge_conditions(
            line_number=None,
            census_year=1950,
            relationship_to_head="Head",
        )
        assert result.first_line_warning is False
        assert result.last_line_warning is False

    def test_unknown_census_year(self):
        """Unknown census year should not trigger warnings."""
        result = detect_edge_conditions(
            line_number=1,
            census_year=1800,  # Pre-1850
            relationship_to_head="Head",
        )
        assert result.first_line_warning is False
        assert result.last_line_warning is False

    def test_1880_census_lines(self):
        """1880 census had 50 lines per sheet."""
        # Line 1
        result = detect_edge_conditions(1, 1880, "Head")
        assert result.first_line_warning is True

        # Line 48-50 (near end)
        result = detect_edge_conditions(48, 1880, "Son")
        assert result.last_line_warning is True

        # Middle line
        result = detect_edge_conditions(25, 1880, "Wife")
        assert result.first_line_warning is False
        assert result.last_line_warning is False


class TestIsEdgeLine:
    """Tests for is_edge_line function."""

    def test_line_1_is_edge(self):
        """Line 1 is always an edge line."""
        assert is_edge_line(1, 1950) is True
        assert is_edge_line(1, 1940) is True
        assert is_edge_line(1, 1880) is True

    def test_last_lines_are_edge(self):
        """Last lines are edge lines."""
        # 1950 census: 30 lines, so 28-30 are edge
        assert is_edge_line(30, 1950) is True
        assert is_edge_line(29, 1950) is True
        assert is_edge_line(28, 1950) is True
        assert is_edge_line(27, 1950) is False

        # 1940 census: 40 lines, so 38-40 are edge
        assert is_edge_line(40, 1940) is True
        assert is_edge_line(39, 1940) is True
        assert is_edge_line(38, 1940) is True
        assert is_edge_line(37, 1940) is False

    def test_middle_lines_not_edge(self):
        """Middle lines are not edge lines."""
        assert is_edge_line(15, 1950) is False
        assert is_edge_line(20, 1940) is False
        assert is_edge_line(25, 1880) is False

    def test_none_line_not_edge(self):
        """None line number is not an edge."""
        assert is_edge_line(None, 1950) is False

    def test_unknown_year_not_edge(self):
        """Unknown year returns False."""
        assert is_edge_line(1, 1800) is False


class TestGetMaxLineForYear:
    """Tests for get_max_line_for_year function."""

    def test_known_years(self):
        """Known census years return correct max lines."""
        assert get_max_line_for_year(1950) == 30
        assert get_max_line_for_year(1940) == 40
        assert get_max_line_for_year(1930) == 100
        assert get_max_line_for_year(1880) == 50
        assert get_max_line_for_year(1850) == 40

    def test_unknown_year(self):
        """Unknown years return None."""
        assert get_max_line_for_year(1800) is None
        assert get_max_line_for_year(2000) is None


class TestEdgeDetectionResult:
    """Tests for EdgeDetectionResult dataclass."""

    def test_default_values(self):
        """Default values are sensible."""
        result = EdgeDetectionResult()
        assert result.first_line_warning is False
        assert result.last_line_warning is False
        assert result.warning_message == ""
        assert result.line_number is None
        assert result.max_line is None

    def test_custom_values(self):
        """Custom values are stored correctly."""
        result = EdgeDetectionResult(
            first_line_warning=True,
            warning_message="Test warning",
            line_number=1,
            max_line=30,
        )
        assert result.first_line_warning is True
        assert result.warning_message == "Test warning"
        assert result.line_number == 1
        assert result.max_line == 30
