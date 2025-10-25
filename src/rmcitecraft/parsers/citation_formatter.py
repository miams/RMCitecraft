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
        """Format citations for 1900-1950 federal census."""
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

        if c.sheet:
            footnote_parts.append(f"sheet {c.sheet},")

        if c.family_number:
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
            f"{state_abbrev}.,",
            "pop. sch.,",
        ]

        if c.town_ward:
            # Simplify town name for short form
            town_short = c.town_ward.split(",")[0]  # Take first part if multiple
            short_parts.append(f"{town_short},")

        if c.enumeration_district:
            short_parts.append(f"E.D. {c.enumeration_district},")

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
            "Population Schedule.",
            "Imaged.",
            f'"{c.census_year} United States Federal Census".',
            "<i>FamilySearch</i>",
            f"{c.familysearch_url} : {year_match.group(1) if year_match else ''}.",
        ]

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
            f"{state_abbrev}.,",
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
