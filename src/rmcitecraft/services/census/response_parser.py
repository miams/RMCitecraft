"""Census response parser for extracting structured data from LLM responses.

This module handles parsing JSON from LLM responses, including handling
markdown code blocks, malformed JSON, and other common issues.
"""

import json
import re
from typing import Any

from loguru import logger


class CensusResponseParser:
    """Parses LLM responses into structured census data.

    Handles various response formats including:
    - Raw JSON
    - JSON in markdown code blocks
    - JSON with explanatory text before/after
    - Malformed JSON with common errors
    """

    def parse_response(self, response_text: str) -> dict[str, Any]:
        """Parse JSON from LLM response.

        Args:
            response_text: Raw response text from LLM

        Returns:
            Parsed dictionary from JSON

        Raises:
            ValueError: If no valid JSON found in response
        """
        if not response_text or not response_text.strip():
            raise ValueError("Empty response from LLM")

        # Try to extract and parse JSON
        json_str = self.extract_json(response_text)

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # Try to fix common JSON errors
            fixed_json = self._fix_common_json_errors(json_str)
            try:
                return json.loads(fixed_json)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON: {e}")
                logger.debug(f"Original text: {json_str[:500]}...")
                raise ValueError(f"Invalid JSON in response: {e}") from e

    def extract_json(self, text: str) -> str:
        """Extract JSON from text, handling various formats.

        Args:
            text: Text that may contain JSON

        Returns:
            Extracted JSON string
        """
        text = text.strip()

        # Try to extract from markdown code block first
        code_block_json = self._extract_from_code_block(text)
        if code_block_json:
            return code_block_json

        # Look for JSON object boundaries
        json_match = self._find_json_object(text)
        if json_match:
            return json_match

        # If text looks like it starts with JSON, return as-is
        if text.startswith("{") or text.startswith("["):
            return text

        raise ValueError("No JSON found in response")

    def _extract_from_code_block(self, text: str) -> str | None:
        """Extract JSON from markdown code block.

        Handles formats like:
        ```json
        {...}
        ```

        or just:
        ```
        {...}
        ```
        """
        # Pattern for ```json ... ``` or ``` ... ```
        patterns = [
            r"```json\s*\n?(.*?)\n?```",
            r"```\s*\n?(.*?)\n?```",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                content = match.group(1).strip()
                if content.startswith("{") or content.startswith("["):
                    return content

        return None

    def _find_json_object(self, text: str) -> str | None:
        """Find JSON object in text by matching braces.

        Args:
            text: Text to search

        Returns:
            JSON string if found, None otherwise
        """
        # Find first { or [
        start_idx = -1
        start_char = None

        for i, char in enumerate(text):
            if char == "{":
                start_idx = i
                start_char = "{"
                break
            elif char == "[":
                start_idx = i
                start_char = "["
                break

        if start_idx == -1:
            return None

        # Match braces to find end
        end_char = "}" if start_char == "{" else "]"
        depth = 0
        in_string = False
        escape_next = False

        for i in range(start_idx, len(text)):
            char = text[i]

            if escape_next:
                escape_next = False
                continue

            if char == "\\":
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == start_char:
                depth += 1
            elif char == end_char:
                depth -= 1
                if depth == 0:
                    return text[start_idx : i + 1]

        # If we didn't find matching end, return from start to end
        return text[start_idx:]

    def _fix_common_json_errors(self, json_str: str) -> str:
        """Fix common JSON errors from LLM responses.

        Args:
            json_str: Potentially malformed JSON

        Returns:
            Fixed JSON string
        """
        fixed = json_str

        # Remove trailing commas before } or ]
        fixed = re.sub(r",\s*([}\]])", r"\1", fixed)

        # Fix unescaped newlines in strings
        # This is tricky - only fix if inside a string value
        # For now, just replace literal newlines with \n
        fixed = re.sub(r'(?<=": ")(.*?)(?=")', lambda m: m.group(1).replace("\n", "\\n"), fixed)

        # Remove control characters that break JSON
        fixed = re.sub(r"[\x00-\x1f]", "", fixed)

        return fixed

    def extract_persons(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract list of persons from parsed response.

        Handles various response structures:
        - {"persons": [...]}
        - {"households": [{"members": [...]}]}
        - Direct list of persons

        Args:
            data: Parsed JSON data

        Returns:
            List of person dictionaries
        """
        # Direct persons array
        if "persons" in data:
            return data["persons"]

        # Households structure
        if "households" in data:
            persons = []
            for household in data["households"]:
                if "members" in household:
                    persons.extend(household["members"])
                elif "persons" in household:
                    persons.extend(household["persons"])
                # For household-only censuses, create pseudo-person from head
                elif "head_of_household" in household:
                    persons.append({
                        "name": household["head_of_household"],
                        "relationship": "Head",
                        **household.get("statistics", {}),
                    })
            return persons

        # Data is already a list
        if isinstance(data, list):
            return data

        # Single person
        if "name" in data:
            return [data]

        return []

    def extract_metadata(self, data: dict[str, Any]) -> dict[str, Any]:
        """Extract metadata from parsed response.

        Args:
            data: Parsed JSON data

        Returns:
            Dictionary with metadata fields
        """
        metadata = {}

        # Check for explicit metadata section
        if "metadata" in data:
            metadata.update(data["metadata"])

        # Also check top-level fields
        for field in [
            "census_year",
            "enumeration_district",
            "sheet",
            "page_number",
            "state",
            "county",
            "township",
        ]:
            if field in data and field not in metadata:
                metadata[field] = data[field]

        return metadata
