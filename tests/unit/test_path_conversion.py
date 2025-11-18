"""
Path conversion tests for RootsMagic symbolic paths.

Tests convert_path_to_rootsmagic_format() function which converts absolute
paths to RootsMagic symbolic format (?/ for media root, ~/ for home).
"""

from pathlib import Path

import pytest

from rmcitecraft.database.findagrave_queries import convert_path_to_rootsmagic_format


class TestConvertPathToRootsMagicFormat:
    """Test path conversion to symbolic format."""

    def test_converts_media_root_path_to_question_mark(self, tmp_path):
        """Verify paths under media_root use ?/ prefix."""
        media_root = tmp_path / "media"
        media_root.mkdir()

        # Create nested path under media root
        test_path = media_root / "Pictures - People" / "Smith, John.jpg"

        result = convert_path_to_rootsmagic_format(test_path, media_root)

        assert result == "?/Pictures - People/Smith, John.jpg"

    def test_converts_home_path_to_tilde(self, tmp_path):
        """Verify paths under home use ~/ prefix."""
        # Create path outside media root but under home
        home_path = Path.home()
        relative_path = Path("Documents") / "test.jpg"

        # Use actual home directory
        test_path = home_path / relative_path

        result = convert_path_to_rootsmagic_format(test_path, tmp_path / "media")

        assert result.startswith("~/")
        assert "Documents/test.jpg" in result

    def test_returns_absolute_for_other_paths(self, tmp_path):
        """Verify paths outside media/home remain absolute."""
        media_root = tmp_path / "media"
        media_root.mkdir()

        # Create path in /tmp (not under media or home)
        other_path = tmp_path / "other" / "test.jpg"

        result = convert_path_to_rootsmagic_format(other_path, media_root)

        # Should return absolute path
        assert str(other_path.resolve()) == result or result.startswith("/")

    def test_handles_nested_subdirectories(self, tmp_path):
        """Verify deep paths converted correctly."""
        media_root = tmp_path / "media"
        media_root.mkdir()

        # Create deeply nested path
        test_path = media_root / "a" / "b" / "c" / "d" / "file.jpg"

        result = convert_path_to_rootsmagic_format(test_path, media_root)

        assert result == "?/a/b/c/d/file.jpg"

    def test_preserves_forward_slashes_posix(self, tmp_path):
        """Verify POSIX path separators in output."""
        media_root = tmp_path / "media"
        media_root.mkdir()

        test_path = media_root / "subfolder" / "file.jpg"

        result = convert_path_to_rootsmagic_format(test_path, media_root)

        # Should use forward slashes (POSIX style)
        assert "/" in result
        assert "\\" not in result
        assert result == "?/subfolder/file.jpg"

    def test_handles_spaces_in_path(self, tmp_path):
        """Verify paths with spaces handled correctly."""
        media_root = tmp_path / "media"
        media_root.mkdir()

        # Path with spaces in directory and filename
        test_path = media_root / "My Photos" / "John Doe.jpg"

        result = convert_path_to_rootsmagic_format(test_path, media_root)

        assert result == "?/My Photos/John Doe.jpg"

    def test_handles_special_characters(self, tmp_path):
        """Verify special characters in filenames preserved."""
        media_root = tmp_path / "media"
        media_root.mkdir()

        # Path with apostrophe and hyphen
        test_path = media_root / "Photos" / "O'Brien-Smith, Mary.jpg"

        result = convert_path_to_rootsmagic_format(test_path, media_root)

        assert result == "?/Photos/O'Brien-Smith, Mary.jpg"

    def test_handles_unicode_characters(self, tmp_path):
        """Verify unicode characters in paths preserved."""
        media_root = tmp_path / "media"
        media_root.mkdir()

        # Path with unicode characters
        test_path = media_root / "Fotos" / "José García.jpg"

        result = convert_path_to_rootsmagic_format(test_path, media_root)

        assert result == "?/Fotos/José García.jpg"

    def test_case_sensitivity(self, tmp_path):
        """Verify case is preserved in paths."""
        media_root = tmp_path / "media"
        media_root.mkdir()

        test_path = media_root / "Pictures - PEOPLE" / "SMITH, John.JPG"

        result = convert_path_to_rootsmagic_format(test_path, media_root)

        assert result == "?/Pictures - PEOPLE/SMITH, John.JPG"

    def test_handles_relative_path_conversion(self, tmp_path):
        """Verify relative paths converted to absolute first."""
        media_root = tmp_path / "media"
        media_root.mkdir()

        # Use relative path
        test_path = Path("media") / "test.jpg"

        # Should resolve to absolute before conversion
        result = convert_path_to_rootsmagic_format(test_path, media_root)

        # Result should still be valid symbolic or absolute
        assert result.startswith("?/") or result.startswith("~/") or result.startswith("/")

    def test_media_root_as_string(self, tmp_path):
        """Verify media_root can be passed as string."""
        media_root = tmp_path / "media"
        media_root.mkdir()

        test_path = media_root / "test.jpg"

        # Pass media_root as string
        result = convert_path_to_rootsmagic_format(str(test_path), str(media_root))

        assert result == "?/test.jpg"

    def test_path_as_string(self, tmp_path):
        """Verify path can be passed as string."""
        media_root = tmp_path / "media"
        media_root.mkdir()

        test_path = media_root / "Photos" / "test.jpg"

        # Pass path as string
        result = convert_path_to_rootsmagic_format(str(test_path), media_root)

        assert result == "?/Photos/test.jpg"

    def test_both_as_strings(self, tmp_path):
        """Verify both path and media_root can be strings."""
        media_root = tmp_path / "media"
        media_root.mkdir()

        test_path = media_root / "test.jpg"

        result = convert_path_to_rootsmagic_format(str(test_path), str(media_root))

        assert result == "?/test.jpg"

    def test_trailing_slash_in_media_root(self, tmp_path):
        """Verify trailing slash in media_root handled correctly."""
        media_root = tmp_path / "media"
        media_root.mkdir()

        test_path = media_root / "test.jpg"

        # Add trailing slash to media_root
        result = convert_path_to_rootsmagic_format(test_path, str(media_root) + "/")

        assert result == "?/test.jpg"

    def test_single_file_in_media_root(self, tmp_path):
        """Verify file directly in media root (no subdirectory)."""
        media_root = tmp_path / "media"
        media_root.mkdir()

        test_path = media_root / "test.jpg"

        result = convert_path_to_rootsmagic_format(test_path, media_root)

        assert result == "?/test.jpg"

    def test_empty_subdirectory_names(self, tmp_path):
        """Verify behavior with minimal path."""
        media_root = tmp_path / "m"
        media_root.mkdir()

        test_path = media_root / "f.jpg"

        result = convert_path_to_rootsmagic_format(test_path, media_root)

        assert result == "?/f.jpg"

    def test_long_path(self, tmp_path):
        """Verify very long paths handled correctly."""
        media_root = tmp_path / "media"
        media_root.mkdir()

        # Create a very long path
        long_subpath = "/".join([f"dir{i}" for i in range(20)])
        test_path = media_root / long_subpath / "file.jpg"

        result = convert_path_to_rootsmagic_format(test_path, media_root)

        assert result.startswith("?/")
        assert result.endswith("/file.jpg")
        assert len(result.split("/")) == 22  # ?/ + 20 dirs + file

    def test_path_with_dots(self, tmp_path):
        """Verify paths with dots (not . or ..) handled correctly."""
        media_root = tmp_path / "media"
        media_root.mkdir()

        # Filename with multiple dots
        test_path = media_root / "Photos" / "file.name.with.dots.jpg"

        result = convert_path_to_rootsmagic_format(test_path, media_root)

        assert result == "?/Photos/file.name.with.dots.jpg"

    def test_media_root_equals_home(self):
        """Verify behavior when media_root is home directory."""
        home_path = Path.home()
        test_path = home_path / "Documents" / "test.jpg"

        result = convert_path_to_rootsmagic_format(test_path, home_path)

        # When media_root IS home, should use ?/ (media takes precedence)
        assert result.startswith("?/")
        assert "Documents/test.jpg" in result
