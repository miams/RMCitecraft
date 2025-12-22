"""Citation formatter for Evidence Explained format.

Generates properly formatted citations for different census years.
"""

from loguru import logger

from rmcitecraft.config import STATE_ABBREVIATIONS
from rmcitecraft.models.citation import ParsedCitation


class CitationFormatter:
    """Format parsed citations according to Evidence Explained standards."""

    def format(
        self,
        citation: ParsedCitation,
    ) -> tuple[str, str, str]:
        """Generate all three citation forms.

        Args:
            citation: Parsed citation data.

        Returns:
            Tuple of (footnote, short_footnote, bibliography).
        """
        year = citation.census_year

        # Select template based on census year
        if year <= 1840:
            return self._format_1790_1840(citation)
        elif year < 1880:
            return self._format_1850_1870(citation)
        elif year == 1880:
            return self._format_1880(citation)
        elif year == 1890:
            return self._format_1890(citation)
        else:  # 1900-1950
            return self._format_1900_1950(citation)

    def generate_source_name_bracket(self, citation: ParsedCitation) -> str:
        """Generate bracket content for SourceTable.Name field.

        Creates the [citing ...] portion based on available citation details.
        Aligns with what appears in the footnote between location and person name.

        Args:
            citation: Parsed citation data

        Returns:
            Bracket content string, e.g., "[citing enumeration district (ED) 16-628, sheet 17, line 16]"

        Examples:
            1900-1950: "[citing enumeration district (ED) 79-215, sheet 4, line 19]"
            1880: "[citing enumeration district (ED) 146, page 92 (stamped), line 9]"
            1850-1870: "[citing sheet 3B, dwelling 123, family 57]"
            1790-1840: "[citing sheet 3B]"
        """
        import re

        year = citation.census_year
        parts = []

        # 1900-1950: ED, sheet, line
        if year >= 1900:
            if citation.enumeration_district:
                parts.append(f"enumeration district (ED) {citation.enumeration_district}")
            if citation.sheet:
                parts.append(f"sheet {citation.sheet}")
            if citation.line:
                parts.append(f"line {citation.line}")

        # 1880: ED, page (stamped), line
        elif year == 1880:
            if citation.enumeration_district:
                parts.append(f"enumeration district (ED) {citation.enumeration_district}")
            if citation.sheet:
                # Remove letter suffix and use page format
                page_num = re.sub(r'[A-Da-d]$', '', str(citation.sheet))
                parts.append(f"page {page_num} (stamped)")
            if citation.line:
                parts.append(f"line {citation.line}")

        # 1850-1870: sheet, dwelling, family (no ED)
        elif year >= 1850:
            if citation.sheet:
                parts.append(f"sheet {citation.sheet}")
            if citation.dwelling_number and citation.family_number:
                parts.append(f"dwelling {citation.dwelling_number}")
                parts.append(f"family {citation.family_number}")
            elif citation.family_number:
                parts.append(f"family {citation.family_number}")

        # 1790-1840: sheet only (minimal info)
        else:
            if citation.sheet:
                parts.append(f"sheet {citation.sheet}")

        if parts:
            return f"[citing {', '.join(parts)}]"
        else:
            return "[]"

    def _format_1900_1950(
        self,
        c: ParsedCitation,
    ) -> tuple[str, str, str]:
        """Format citations for 1900-1950 federal census.

        Reference: Mills, Elizabeth Shown. Evidence Explained: Citing History Sources
        from Artifacts to Cyberspace: 4th Edition (p. 253).

        Note: For 1910-1940, only population schedules survived, so "population schedule"
        is omitted as redundant. Line number is included when available.
        """
        import re

        # Footnote
        footnote_parts = [
            f"{c.census_year} U.S. census,",
            f"{c.county} County,",
            f"{c.state},",
        ]

        # 1910-1950: Omit "population schedule" (only population schedules survived)
        # 1900: Include "population schedule" (multiple schedule types existed)
        if c.census_year == 1900:
            footnote_parts.append("population schedule,")

        if c.town_ward:
            footnote_parts.append(f"{c.town_ward},")

        if c.enumeration_district:
            footnote_parts.append(f"enumeration district (ED) {c.enumeration_district},")

        if c.sheet:
            footnote_parts.append(f"sheet {c.sheet},")

        # Family number (1900 census may include this)
        if c.family_number:
            footnote_parts.append(f"family {c.family_number},")

        # Line number (when available)
        if c.line:
            footnote_parts.append(f"line {c.line},")

        footnote_parts.append(f"{c.person_name};")

        # Add FamilySearch citation - correct format per Evidence Explained
        # Collection title format: "United States, Census, YYYY" per FamilySearch official naming
        footnote_parts.append(
            f'imaged, "United States, Census, {c.census_year}," '
            f"<i>FamilySearch</i>, ({c.familysearch_url} : accessed {c.access_date})."
        )

        footnote = " ".join(footnote_parts)

        # Short Footnote
        # Note: "pop. sch." omitted for 1910-1940 (only population schedules survived)
        from rmcitecraft.config.constants import LOCALITY_TYPE_ABBREVIATIONS

        state_abbrev = STATE_ABBREVIATIONS.get(c.state, c.state[:2].upper())
        short_parts = [
            f"{c.census_year} U.S. census,",
            f"{c.county} Co.,",
            f"{state_abbrev},",
        ]

        # For 1910-1950: Omit "pop. sch." (only population schedules survived)
        # For 1900: Include "pop. sch." (multiple schedule types existed)
        if c.census_year == 1900:
            short_parts.append("pop. sch.,")

        if c.town_ward:
            # Parse locality and type, then abbreviate the type
            # For short footnotes, use only the first locality component
            # e.g., "Olive Township Caldwell village" → "Olive Township"
            # e.g., "Baltimore Ward 13" → "Baltimore Ward 13"

            # Try to find the first locality type (Township, Ward, etc.)
            town_ward_clean = c.town_ward
            for locality_type in LOCALITY_TYPE_ABBREVIATIONS.keys():
                if locality_type in c.town_ward:
                    # Extract up to and including this type
                    parts = c.town_ward.split(locality_type, 1)
                    if len(parts) == 2:
                        town_ward_clean = (parts[0] + locality_type).strip()
                    break

            # Now abbreviate the type
            town_parts = town_ward_clean.rsplit(" ", 1)  # Split from right
            if len(town_parts) == 2:
                locality, locality_type = town_parts
                # Check if second part is a known type
                if locality_type in LOCALITY_TYPE_ABBREVIATIONS:
                    type_abbrev = LOCALITY_TYPE_ABBREVIATIONS[locality_type]
                    short_parts.append(f"{locality} {type_abbrev},")
                else:
                    # Not a known type, use as-is
                    short_parts.append(f"{town_ward_clean},")
            else:
                # No type, just locality name
                short_parts.append(f"{town_ward_clean},")

        if c.enumeration_district:
            short_parts.append(f"E.D. {c.enumeration_district},")

        if c.sheet:
            short_parts.append(f"sheet {c.sheet},")

        if c.family_number:
            short_parts.append(f"family {c.family_number},")

        if c.line:
            short_parts.append(f"line {c.line},")

        short_parts.append(f"{c.person_name}.")

        short_footnote = " ".join(short_parts)

        # Bibliography
        # Extract year from access date (e.g., "24 July 2015" -> "2015")
        year_match = None
        if c.access_date:
            year_match = re.search(r'\b(\d{4})\b', c.access_date)

        bib_parts = [
            "U.S.",
            f"{c.state}.",
            f"{c.county} County.",
            f"{c.census_year} U.S Census.",
        ]

        # 1910-1950: Omit "Population Schedule." (only population schedules survived)
        # 1900: Include "Population Schedule." (multiple schedule types existed)
        if c.census_year == 1900:
            bib_parts.append("Population Schedule.")

        bib_parts.extend([
            "Imaged.",
            f'"United States, Census, {c.census_year}."',
            "<i>FamilySearch</i>",
            f"{c.familysearch_url} : {year_match.group(1) if year_match else ''}.",
        ])

        bibliography = " ".join(bib_parts)

        logger.debug(f"Formatted citation {c.citation_id} ({c.census_year})")

        return footnote, short_footnote, bibliography

    def _format_1850_1870(
        self,
        c: ParsedCitation,
    ) -> tuple[str, str, str]:
        """Format citations for 1850-1870 federal census."""
        # Footnote
        footnote_parts = [
            f"{c.census_year} U.S. census,",
            f"{c.county} County,",
            f"{c.state},",
            "population schedule,",
        ]

        if c.town_ward:
            footnote_parts.append(f"{c.town_ward},")

        if c.sheet:
            footnote_parts.append(f"sheet {c.sheet},")

        # 1850-1880 used dwelling/family, not just family
        if c.dwelling_number and c.family_number:
            footnote_parts.append(f"dwelling {c.dwelling_number}, family {c.family_number},")
        elif c.family_number:
            footnote_parts.append(f"family {c.family_number},")

        footnote_parts.append(f"{c.person_name};")

        # Add FamilySearch citation - FamilySearch official naming
        footnote_parts.append(
            f'imaged, "United States, Census, {c.census_year}," '
            f"<i>FamilySearch</i> ({c.familysearch_url} : accessed {c.access_date})."
        )

        footnote = " ".join(footnote_parts)

        # Short Footnote
        state_abbrev = STATE_ABBREVIATIONS.get(c.state, c.state[:2].upper())
        short_parts = [
            f"{c.census_year} U.S. census,",
            f"{c.county} Co.,",
            f"{state_abbrev},",
            "pop. sch.,",
        ]

        if c.town_ward:
            town_short = c.town_ward.split(",")[0]
            short_parts.append(f"{town_short},")

        if c.sheet:
            short_parts.append(f"sheet {c.sheet},")

        short_parts.append(f"{c.person_name}.")

        short_footnote = " ".join(short_parts)

        # Bibliography
        bib_parts = [
            "U.S.",
            f"{c.state}.",
            f"{c.county} County.",
            f"{c.census_year} U.S Census.",
            "Population Schedule.",
            "Imaged.",
            f'"United States, Census, {c.census_year}."',
            "<i>FamilySearch</i>",
            f"{c.familysearch_url} : {c.access_date[:4] if c.access_date else ''}.",
        ]

        bibliography = " ".join(bib_parts)

        return footnote, short_footnote, bibliography

    def _format_1880(
        self,
        c: ParsedCitation,
    ) -> tuple[str, str, str]:
        """Format citations for 1880 federal census.

        1880 uses stamped page numbers (not sheet numbers with letter suffixes).
        Format: "page X (stamped)" in footnote, "p. X (stamped)" in short footnote.
        ED was introduced in 1880.
        """
        import re

        # Footnote
        footnote_parts = [
            f"{c.census_year} U.S. census,",
            f"{c.county} County,",
            f"{c.state},",
            "population schedule,",
        ]

        if c.town_ward:
            footnote_parts.append(f"{c.town_ward},")

        if c.enumeration_district:
            footnote_parts.append(f"enumeration district (ED) {c.enumeration_district},")

        # 1880 uses stamped page numbers (no letter suffix)
        if c.sheet:
            # Remove any letter suffix if present and use "page (stamped)" format
            page_num = re.sub(r'[A-Da-d]$', '', str(c.sheet))
            footnote_parts.append(f"page {page_num} (stamped),")

        if c.line:
            footnote_parts.append(f"line {c.line},")

        footnote_parts.append(f"{c.person_name};")

        # Add FamilySearch citation
        footnote_parts.append(
            f'imaged, "United States, Census, {c.census_year}," '
            f"<i>FamilySearch</i> ({c.familysearch_url} : accessed {c.access_date})."
        )

        footnote = " ".join(footnote_parts)

        # Short Footnote
        from rmcitecraft.config.constants import LOCALITY_TYPE_ABBREVIATIONS

        state_abbrev = STATE_ABBREVIATIONS.get(c.state, c.state[:2].upper())
        short_parts = [
            f"{c.census_year} U.S. census,",
            f"{c.county} Co.,",
            f"{state_abbrev},",
            "pop. sch.,",
        ]

        if c.town_ward:
            # Abbreviate locality type for short footnote
            town_ward_clean = c.town_ward
            for locality_type in LOCALITY_TYPE_ABBREVIATIONS.keys():
                if locality_type in c.town_ward:
                    parts = c.town_ward.split(locality_type, 1)
                    if len(parts) == 2:
                        town_ward_clean = (parts[0] + locality_type).strip()
                    break

            town_parts = town_ward_clean.rsplit(" ", 1)
            if len(town_parts) == 2:
                locality, locality_type = town_parts
                if locality_type in LOCALITY_TYPE_ABBREVIATIONS:
                    type_abbrev = LOCALITY_TYPE_ABBREVIATIONS[locality_type]
                    short_parts.append(f"{locality} {type_abbrev},")
                else:
                    short_parts.append(f"{town_ward_clean},")
            else:
                short_parts.append(f"{town_ward_clean},")

        if c.enumeration_district:
            short_parts.append(f"E.D. {c.enumeration_district},")

        # 1880 uses "p. X (stamped)" in short footnote
        if c.sheet:
            page_num = re.sub(r'[A-Da-d]$', '', str(c.sheet))
            short_parts.append(f"p. {page_num} (stamped),")

        if c.line:
            short_parts.append(f"line {c.line},")

        short_parts.append(f"{c.person_name}.")

        short_footnote = " ".join(short_parts)

        # Bibliography
        year_match = None
        if c.access_date:
            year_match = re.search(r'\b(\d{4})\b', c.access_date)

        bib_parts = [
            "U.S.",
            f"{c.state}.",
            f"{c.county} County.",
            f"{c.census_year} U.S. Census.",
            "Population Schedule.",
            "Imaged.",
            f'"United States, Census, {c.census_year}."',
            "<i>FamilySearch</i>",
            f"{c.familysearch_url} : {year_match.group(1) if year_match else ''}.",
        ]

        bibliography = " ".join(bib_parts)

        logger.debug(f"Formatted 1880 citation {c.citation_id}")

        return footnote, short_footnote, bibliography

    def _format_1790_1840(
        self,
        c: ParsedCitation,
    ) -> tuple[str, str, str]:
        """Format citations for 1790-1840 federal census."""
        # Footnote (simpler, no population schedule, no ED)
        footnote_parts = [
            f"{c.census_year} U.S. census,",
            f"{c.county} County,",
            f"{c.state},",
        ]

        if c.town_ward:
            footnote_parts.append(f"{c.town_ward},")

        if c.sheet:
            footnote_parts.append(f"sheet {c.sheet},")

        footnote_parts.append(f"{c.person_name};")

        # Add FamilySearch citation - FamilySearch official naming
        footnote_parts.append(
            f'imaged, "United States, Census, {c.census_year}," '
            f"<i>FamilySearch</i> ({c.familysearch_url} : accessed {c.access_date})."
        )

        footnote = " ".join(footnote_parts)

        # Short Footnote
        state_abbrev = STATE_ABBREVIATIONS.get(c.state, c.state[:2].upper())
        short_parts = [
            f"{c.census_year} U.S. census,",
            f"{c.county} Co.,",
            f"{state_abbrev}.,",
        ]

        if c.town_ward:
            town_short = c.town_ward.split(",")[0]
            short_parts.append(f"{town_short},")

        if c.sheet:
            short_parts.append(f"sheet {c.sheet},")

        short_parts.append(f"{c.person_name}.")

        short_footnote = " ".join(short_parts)

        # Bibliography
        bib_parts = [
            "U.S.",
            f"{c.state}.",
            f"{c.county} County.",
            f"{c.census_year} U.S Census.",
            "Imaged.",
            f'"United States, Census, {c.census_year}."',
            "<i>FamilySearch</i>",
            f"{c.familysearch_url} : {c.access_date[:4] if c.access_date else ''}.",
        ]

        bibliography = " ".join(bib_parts)

        return footnote, short_footnote, bibliography

    def _format_1890(
        self,
        c: ParsedCitation,
    ) -> tuple[str, str, str]:
        """Format citations for 1890 federal census (special case - mostly destroyed)."""
        # 1890 is similar to 1900-1950 but with special note
        return self._format_1900_1950(c)
