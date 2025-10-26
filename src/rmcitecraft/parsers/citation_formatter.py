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
        elif year <= 1880:
            return self._format_1850_1880(citation)
        elif year == 1890:
            return self._format_1890(citation)
        else:  # 1900-1950
            return self._format_1900_1950(citation)

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

        # 1910-1940: Omit "population schedule" (only schedules that survived)
        # 1900 and 1950: Include "population schedule" if multiple schedule types exist
        if c.census_year in [1900, 1950]:
            footnote_parts.append("population schedule,")

        if c.town_ward:
            footnote_parts.append(f"{c.town_ward},")

        if c.enumeration_district:
            footnote_parts.append(f"enumeration district (ED) {c.enumeration_district},")

        if c.sheet:
            footnote_parts.append(f"sheet {c.sheet},")

        # Line number (not family number) per Evidence Explained
        if c.line:
            footnote_parts.append(f"line {c.line},")

        footnote_parts.append(f"{c.person_name};")

        # Add FamilySearch citation - correct format per Evidence Explained
        # Collection title format: "United States Census, YYYY" (not "YYYY United States Federal Census")
        footnote_parts.append(
            f'imaged, "United States Census, {c.census_year}," '
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

        # For 1900 and 1950: Include "pop. sch." (multiple schedule types)
        # For 1910-1940: Omit "pop. sch." (only population schedules survived)
        if c.census_year in [1900, 1950]:
            short_parts.append("pop. sch.,")

        if c.town_ward:
            # Parse locality and type, then abbreviate the type
            # town_ward may be "Jefferson Township" or just "Jefferson"
            town_parts = c.town_ward.rsplit(" ", 1)  # Split from right
            if len(town_parts) == 2:
                locality, locality_type = town_parts
                # Check if second part is a known type
                if locality_type in LOCALITY_TYPE_ABBREVIATIONS:
                    type_abbrev = LOCALITY_TYPE_ABBREVIATIONS[locality_type]
                    short_parts.append(f"{locality} {type_abbrev},")
                else:
                    # Not a known type, use as-is
                    short_parts.append(f"{c.town_ward},")
            else:
                # No type, just locality name
                short_parts.append(f"{c.town_ward},")

        if c.enumeration_district:
            short_parts.append(f"ED {c.enumeration_district},")

        if c.sheet:
            short_parts.append(f"sheet {c.sheet},")

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

        # 1910-1940: Omit "Population Schedule." (only schedules that survived)
        if c.census_year in [1900, 1950]:
            bib_parts.append("Population Schedule.")

        bib_parts.extend([
            "Imaged.",
            f'"{c.census_year} United States Federal Census."',
            "<i>FamilySearch</i>",
            f"{c.familysearch_url} : {year_match.group(1) if year_match else ''}.",
        ])

        bibliography = " ".join(bib_parts)

        logger.debug(f"Formatted citation {c.citation_id} ({c.census_year})")

        return footnote, short_footnote, bibliography

    def _format_1850_1880(
        self,
        c: ParsedCitation,
    ) -> tuple[str, str, str]:
        """Format citations for 1850-1880 federal census."""
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

        # Add FamilySearch citation
        footnote_parts.append(
            f'imaged, "{c.census_year} United States Federal Census," '
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
            f'"{c.census_year} United States Federal Census".',
            "<i>FamilySearch</i>",
            f"{c.familysearch_url} : {c.access_date[:4] if c.access_date else ''}.",
        ]

        bibliography = " ".join(bib_parts)

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

        # Add FamilySearch citation
        footnote_parts.append(
            f'imaged, "{c.census_year} United States Federal Census," '
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
            f'"{c.census_year} United States Federal Census".',
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
