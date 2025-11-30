"""Census prompt builder for constructing LLM transcription prompts.

This module builds detailed prompts from census schemas, including
targeting hints for specific households or individuals.
"""

import json

from rmcitecraft.models.census_schema import CensusEra, CensusYearSchema


class CensusPromptBuilder:
    """Builds LLM prompts from census schemas.

    The prompt builder constructs comprehensive transcription prompts that include:
    - Year-specific instructions from the schema
    - JSON schema for structured output
    - Targeting hints for specific households/individuals
    - Transcription rules and abbreviation guides
    """

    def build_transcription_prompt(
        self,
        schema: CensusYearSchema,
        target_names: list[str] | None = None,
        target_line: int | None = None,
        sheet: str | None = None,
        enumeration_district: str | None = None,
    ) -> str:
        """Build complete transcription prompt from schema.

        Args:
            schema: Census year schema
            target_names: Names to look for (helps LLM focus)
            target_line: Specific line number to find
            sheet: Sheet number (for 1880-1940)
            enumeration_district: ED number

        Returns:
            Complete prompt string for LLM
        """
        sections = [
            self._build_header_section(schema),
            self._build_schema_section(schema),
            self._build_targeting_section(
                schema, target_names, target_line, sheet, enumeration_district
            ),
            self._build_instructions_section(schema),
            self._build_rules_section(schema),
        ]

        return "\n\n".join(section for section in sections if section)

    def _build_header_section(self, schema: CensusYearSchema) -> str:
        """Build the header with task description."""
        era_descriptions = {
            CensusEra.HOUSEHOLD_ONLY: (
                "This is an early census where ONLY the head of household is named. "
                "Other household members are recorded as statistical tallies by age/sex."
            ),
            CensusEra.INDIVIDUAL_NO_ED: (
                "This census names every individual but does NOT use enumeration districts. "
                "Use page number for citations."
            ),
            CensusEra.INDIVIDUAL_WITH_ED_SHEET: (
                "This census names every individual and uses enumeration districts with sheet numbers. "
                "Include ED and sheet in transcription."
            ),
            CensusEra.INDIVIDUAL_WITH_ED_PAGE: (
                "This is the 1950 census which names every individual, uses enumeration districts, "
                "and returns to page numbers (called 'stamp' in citations)."
            ),
        }

        era_desc = era_descriptions.get(schema.era, "")

        return f"""TASK: Transcribe the {schema.year} United States Federal Census image.

{era_desc}

Extract all visible information from the census page and return it as structured JSON."""

    def _build_schema_section(self, schema: CensusYearSchema) -> str:
        """Build the JSON schema section showing expected output format."""
        # Build a sample schema object
        json_schema = schema.to_json_schema()

        # For household-only censuses, simplify the schema
        if schema.era == CensusEra.HOUSEHOLD_ONLY:
            return f"""OUTPUT FORMAT:
Return a JSON object with this structure:

```json
{{
  "page_number": <integer>,
  "households": [
    {{
      "head_of_household": "<name>",
      "statistics": {{
        // Age/sex category tallies from the form
      }}
    }}
  ]
}}
```"""

        # For individual censuses, show full structure
        sample_person = {k: f"<{v.split(' - ')[0]}>" for k, v in json_schema.items()}

        return f"""OUTPUT FORMAT:
Return a JSON object with this structure:

```json
{{
  "metadata": {{
    "census_year": {schema.year},
    "enumeration_district": "<string or null>",
    "sheet": "<string or null>",
    "page_number": <integer or null>
  }},
  "persons": [
    {json.dumps(sample_person, indent=6)}
  ]
}}
```

FIELD DEFINITIONS:
{self._format_field_definitions(schema)}"""

    def _format_field_definitions(self, schema: CensusYearSchema) -> str:
        """Format field definitions for prompt."""
        lines = []
        for col in schema.columns:
            line = f"- {col.name}: {col.description}"
            if col.valid_values:
                line += f" (values: {', '.join(col.valid_values)})"
            if col.required:
                line += " [REQUIRED]"
            lines.append(line)
        return "\n".join(lines)

    def _build_targeting_section(
        self,
        schema: CensusYearSchema,
        target_names: list[str] | None,
        target_line: int | None,
        sheet: str | None,
        enumeration_district: str | None,
    ) -> str:
        """Build targeting hints section."""
        hints = []

        if target_names:
            names_str = ", ".join(target_names)
            hints.append(f"PRIORITY: Look for these names: {names_str}")
            hints.append(
                "Focus on extracting the household containing these individuals first."
            )

        if target_line:
            hints.append(f"TARGET LINE: Focus on line {target_line} and nearby lines.")
            hints.append(
                "Extract the complete household that includes this line number."
            )

        if sheet:
            hints.append(f"SHEET: This should be sheet {sheet}.")

        if enumeration_district:
            hints.append(f"ENUMERATION DISTRICT: This should be ED {enumeration_district}.")

        if not hints:
            return ""

        return "TARGETING HINTS:\n" + "\n".join(hints)

    def _build_instructions_section(self, schema: CensusYearSchema) -> str:
        """Build year-specific instructions from schema."""
        if not schema.instructions:
            return ""

        return f"YEAR-SPECIFIC INSTRUCTIONS:\n{schema.instructions}"

    def _build_rules_section(self, schema: CensusYearSchema) -> str:
        """Build transcription rules from schema."""
        rules = [
            "TRANSCRIPTION RULES:",
            "1. Transcribe names EXACTLY as written, preserving original spelling",
            "2. Use null for fields that are blank or illegible",
            "3. Expand common abbreviations when clear (Wm→William, Jno→John)",
            "4. For ditto marks (\" or do), use the value from the line above",
        ]

        # Add abbreviation guide if available
        if schema.abbreviations:
            abbrev_lines = [f"   {k} = {v}" for k, v in schema.abbreviations.items()]
            rules.append("5. Common abbreviations in this census:")
            rules.extend(abbrev_lines)

        # Add era-specific rules
        if schema.era == CensusEra.HOUSEHOLD_ONLY:
            rules.append(
                "6. IMPORTANT: Only the head of household has a name. "
                "Other household members are statistical tallies."
            )
        elif schema.era == CensusEra.INDIVIDUAL_NO_ED:
            rules.append("6. Use page_number (not sheet) for location reference.")
        elif schema.era == CensusEra.INDIVIDUAL_WITH_ED_SHEET:
            rules.append(
                "6. Include both enumeration_district and sheet (e.g., '3A' or '3B')."
            )
        elif schema.era == CensusEra.INDIVIDUAL_WITH_ED_PAGE:
            rules.append(
                "6. Use page_number (called 'stamp' in citations) with enumeration_district."
            )

        rules.append(
            "7. Return ONLY the JSON object, no explanatory text before or after."
        )

        return "\n".join(rules)

    def build_family_extraction_prompt(
        self,
        schema: CensusYearSchema,
        target_names: list[str],
    ) -> str:
        """Build prompt specifically for extracting a family group.

        Used when we know specific names and want to extract their complete
        household including all family members.

        Args:
            schema: Census year schema
            target_names: Names of people to find

        Returns:
            Prompt optimized for family extraction
        """
        names_str = ", ".join(target_names)

        return f"""TASK: Extract the complete household containing: {names_str}

Census Year: {schema.year}

INSTRUCTIONS:
1. Find the household containing the named individual(s)
2. Extract ALL persons in that household (same dwelling/family number)
3. Include household metadata (ED, sheet/page, line numbers)

{self._build_schema_section(schema)}

{self._build_rules_section(schema)}

Return the complete household as JSON."""
