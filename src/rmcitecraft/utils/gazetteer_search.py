"""
RootsMagic Gazetteer (PlaceDB.dat) search utility.

The PlaceDB.dat file is a proprietary format gazetteer database shipped with RootsMagic.
While we cannot fully parse the binary format, we can search for place names within it
to validate and suggest place names.

File location: /Applications/RootsMagic 11.app/Contents/MacOS/PlaceDB.dat
"""

import re
from pathlib import Path
from typing import List, Optional
from difflib import SequenceMatcher


class GazetteerSearch:
    """Search utility for RootsMagic gazetteer database."""

    DEFAULT_PATH = "/Applications/RootsMagic 11.app/Contents/MacOS/PlaceDB.dat"

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize gazetteer search.

        Args:
            db_path: Path to PlaceDB.dat file. Uses default location if None.
        """
        self.db_path = Path(db_path) if db_path else Path(self.DEFAULT_PATH)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Gazetteer not found: {self.db_path}")

    def search(
        self,
        search_term: str,
        case_sensitive: bool = False,
        max_results: int = 50
    ) -> List[str]:
        """
        Search for place names in the gazetteer.

        Args:
            search_term: Place name to search for
            case_sensitive: Whether search should be case-sensitive
            max_results: Maximum number of results to return

        Returns:
            List of matching place names (may include metadata artifacts)
        """
        matches = set()

        with open(self.db_path, 'rb') as f:
            chunk_size = 1024 * 1024  # 1MB chunks
            overlap = 200  # Overlap to catch matches spanning chunks
            previous_chunk = b''

            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break

                search_data = previous_chunk + chunk

                # Create search pattern
                if case_sensitive:
                    pattern = re.compile(re.escape(search_term).encode('latin-1'))
                else:
                    pattern = re.compile(
                        re.escape(search_term).encode('latin-1'),
                        re.IGNORECASE
                    )

                # Find matches and extract context
                for match in pattern.finditer(search_data):
                    place_name = self._extract_place_name(
                        search_data,
                        match.start(),
                        len(search_term)
                    )
                    if place_name:
                        matches.add(place_name)

                    if len(matches) >= max_results:
                        return sorted(list(matches))[:max_results]

                previous_chunk = chunk[-overlap:] if len(chunk) >= overlap else chunk

                if len(chunk) < chunk_size:
                    break

        return sorted(list(matches))[:max_results]

    def _extract_place_name(
        self,
        data: bytes,
        match_pos: int,
        search_len: int
    ) -> Optional[str]:
        """
        Extract full place name from match position.

        Attempts to find printable ASCII characters before and after match.
        """
        # Extract context around match
        start = max(0, match_pos - 50)
        end = min(len(data), match_pos + search_len + 50)
        context = data[start:end]

        # Find printable characters before match
        rel_match_pos = match_pos - start
        before = ''
        for i in range(rel_match_pos - 1, -1, -1):
            if 32 <= context[i] <= 126:  # Printable ASCII
                before = chr(context[i]) + before
            else:
                break

        # Find printable characters after match
        after = ''
        for i in range(rel_match_pos + search_len, len(context)):
            if 32 <= context[i] <= 126:
                after += chr(context[i])
            else:
                break

        # Reconstruct full match
        matched_text = context[rel_match_pos:rel_match_pos + search_len].decode(
            'latin-1', errors='replace'
        )
        full_match = (before + matched_text + after).strip()

        # Filter out artifacts (single chars, non-alphanumeric, etc.)
        if len(full_match) >= 2 and any(c.isalnum() for c in full_match):
            return full_match

        return None

    def exists(self, place_name: str, fuzzy: bool = False, threshold: float = 0.90) -> bool:
        """
        Check if a place exists in the gazetteer.

        Args:
            place_name: Place name to check
            fuzzy: Use fuzzy matching
            threshold: Similarity threshold for fuzzy matching (0.0-1.0)

        Returns:
            True if place exists (or close match found if fuzzy=True)
        """
        matches = self.search(place_name, case_sensitive=False, max_results=10)

        if not matches:
            return False

        if not fuzzy:
            # Exact match (case-insensitive)
            return any(m.lower() == place_name.lower() for m in matches)

        # Fuzzy match
        for match in matches:
            similarity = SequenceMatcher(
                None,
                place_name.lower(),
                match.lower()
            ).ratio()
            if similarity >= threshold:
                return True

        return False

    def suggest_places(
        self,
        partial_name: str,
        max_suggestions: int = 10
    ) -> List[str]:
        """
        Get place name suggestions based on partial input.

        Args:
            partial_name: Partial place name
            max_suggestions: Maximum suggestions to return

        Returns:
            List of suggested place names
        """
        if len(partial_name) < 2:
            return []

        return self.search(
            partial_name,
            case_sensitive=False,
            max_results=max_suggestions
        )

    def validate_hierarchy(self, city: str, state: str, country: str) -> dict:
        """
        Validate a place hierarchy against gazetteer.

        Args:
            city: City/town name
            state: State/province name
            country: Country name

        Returns:
            Dict with validation results for each component
        """
        return {
            'city': self.exists(city, fuzzy=True),
            'state': self.exists(state, fuzzy=True),
            'country': self.exists(country, fuzzy=True),
            'city_exact': self.exists(city, fuzzy=False),
            'state_exact': self.exists(state, fuzzy=False),
            'country_exact': self.exists(country, fuzzy=False),
        }


# Convenience functions
def search_gazetteer(search_term: str, max_results: int = 50) -> List[str]:
    """
    Quick search of RootsMagic gazetteer.

    Args:
        search_term: Place name to search
        max_results: Maximum results

    Returns:
        List of matching place names
    """
    searcher = GazetteerSearch()
    return searcher.search(search_term, max_results=max_results)


def validate_place(place_name: str, fuzzy: bool = True) -> bool:
    """
    Check if place exists in RootsMagic gazetteer.

    Args:
        place_name: Place name to validate
        fuzzy: Use fuzzy matching

    Returns:
        True if place exists
    """
    searcher = GazetteerSearch()
    return searcher.exists(place_name, fuzzy=fuzzy)
