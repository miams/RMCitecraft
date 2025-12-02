"""Census Form Renderer Service.

Renders census form data to HTML using Jinja2 templates.
This service combines the data layer (CensusFormDataService) with
Jinja2 templates to produce viewable HTML output.

Usage:
    renderer = CensusFormRenderer()
    html = renderer.render_page(page_id=123)
    # or
    html = renderer.render_for_person(person_id=456)
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger

from rmcitecraft.models.census_form_data import CensusFormContext
from rmcitecraft.services.census_form_service import (
    CensusFormDataService,
    get_form_service,
)


# Template directory paths
TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "census" / "jinja"
STATIC_DIR = Path(__file__).parent.parent / "templates" / "census" / "static"


class CensusFormRenderer:
    """Renders census forms to HTML using Jinja2 templates."""

    def __init__(
        self,
        data_service: CensusFormDataService | None = None,
        templates_dir: Path | None = None,
    ):
        """Initialize renderer with optional custom paths.

        Args:
            data_service: Data service for loading form data
            templates_dir: Custom templates directory path
        """
        self.data_service = data_service or get_form_service()
        self.templates_dir = templates_dir or TEMPLATES_DIR

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        self._register_filters()

    def _register_filters(self) -> None:
        """Register custom Jinja2 filters."""

        def format_income(value: str | int | None) -> str:
            """Format income values with $ prefix."""
            if value is None or value == "":
                return ""
            try:
                num = int(str(value).replace("$", "").replace(",", ""))
                return f"${num:,}"
            except (ValueError, TypeError):
                return str(value)

        def ditto_if_same(value: str, prev_value: str) -> str:
            """Return ditto mark if value same as previous."""
            if value and value == prev_value:
                return '"'
            return value

        self.env.filters["format_income"] = format_income
        self.env.filters["ditto_if_same"] = ditto_if_same

    def render_page(
        self,
        page_id: int,
        include_quality: bool = True,
        include_sample_columns: bool = True,
        embed_css: bool = False,
    ) -> str:
        """Render a census page to HTML.

        Args:
            page_id: Database page_id
            include_quality: Show quality indicators
            include_sample_columns: Show sample line columns (1950)
            embed_css: Embed CSS inline instead of linking

        Returns:
            Rendered HTML string
        """
        context = self.data_service.load_form_context(
            page_id=page_id,
            include_quality=include_quality,
            include_sample_columns=include_sample_columns,
        )

        if not context:
            logger.warning(f"No data found for page_id={page_id}")
            return self._render_error(f"Page not found: {page_id}")

        return self._render_context(context, embed_css=embed_css)

    def render_for_person(
        self,
        person_id: int,
        include_household: bool = True,
        include_quality: bool = True,
        embed_css: bool = False,
    ) -> str:
        """Render census form centered on a specific person.

        Args:
            person_id: Database person_id
            include_household: Include full household
            include_quality: Show quality indicators
            embed_css: Embed CSS inline

        Returns:
            Rendered HTML string
        """
        context = self.data_service.load_form_context_for_person(
            person_id=person_id,
            include_household=include_household,
            include_quality=include_quality,
        )

        if not context:
            logger.warning(f"No data found for person_id={person_id}")
            return self._render_error(f"Person not found: {person_id}")

        return self._render_context(context, embed_css=embed_css)

    def render_multi_page(
        self,
        page_ids: list[int],
        include_quality: bool = True,
        embed_css: bool = False,
    ) -> str:
        """Render multiple census pages (for cross-page families).

        Args:
            page_ids: List of page_ids to render
            include_quality: Show quality indicators
            embed_css: Embed CSS inline

        Returns:
            Rendered HTML string
        """
        context = self.data_service.load_multi_page_context(
            page_ids=page_ids,
            include_quality=include_quality,
        )

        if not context:
            logger.warning(f"No data found for page_ids={page_ids}")
            return self._render_error(f"Pages not found: {page_ids}")

        return self._render_context(context, embed_css=embed_css)

    def render_from_context(
        self,
        context: CensusFormContext,
        embed_css: bool = False,
    ) -> str:
        """Render HTML from a pre-built context.

        Args:
            context: CensusFormContext object
            embed_css: Embed CSS inline

        Returns:
            Rendered HTML string
        """
        return self._render_context(context, embed_css=embed_css)

    def _render_context(
        self,
        context: CensusFormContext,
        embed_css: bool = False,
    ) -> str:
        """Internal method to render a context object."""
        # Select template based on census year
        template_name = self._get_template_name(context.census_year)

        try:
            template = self.env.get_template(template_name)
        except Exception as e:
            logger.error(f"Template not found: {template_name}: {e}")
            return self._render_error(f"Template not found for year {context.census_year}")

        # Build template context
        template_context = {
            "ctx": context,
            "embed_css": embed_css,
        }

        # Add embedded CSS if requested
        if embed_css:
            template_context["css_content"] = self._load_css()

        return template.render(**template_context)

    def _get_template_name(self, census_year: int) -> str:
        """Get the template filename for a census year."""
        template_path = self.templates_dir / f"{census_year}.html"
        if template_path.exists():
            return f"{census_year}.html"

        # Fall back to era-based templates
        if census_year >= 1950:
            return "1950.html"
        elif census_year >= 1880:
            return "1880_1940.html"  # TODO: Create this
        elif census_year >= 1850:
            return "1850_1870.html"  # TODO: Create this
        else:
            return "1790_1840.html"  # TODO: Create this

    def _load_css(self) -> str:
        """Load CSS content for embedding."""
        css_path = STATIC_DIR / "census_forms.css"
        if css_path.exists():
            return css_path.read_text()
        logger.warning(f"CSS file not found: {css_path}")
        return ""

    def _render_error(self, message: str) -> str:
        """Render an error page."""
        return f"""<!DOCTYPE html>
<html>
<head><title>Error</title></head>
<body>
<h1>Error</h1>
<p>{message}</p>
</body>
</html>"""

    def get_css_path(self) -> Path:
        """Get path to the CSS file for external linking."""
        return STATIC_DIR / "census_forms.css"


# =============================================================================
# Convenience Functions
# =============================================================================


def render_census_page(page_id: int, embed_css: bool = False) -> str:
    """Render a census page to HTML.

    Convenience function for quick rendering.

    Args:
        page_id: Database page_id
        embed_css: Embed CSS inline

    Returns:
        Rendered HTML string
    """
    renderer = CensusFormRenderer()
    return renderer.render_page(page_id, embed_css=embed_css)


def render_census_for_person(person_id: int, embed_css: bool = False) -> str:
    """Render census form for a specific person.

    Convenience function for quick rendering.

    Args:
        person_id: Database person_id
        embed_css: Embed CSS inline

    Returns:
        Rendered HTML string
    """
    renderer = CensusFormRenderer()
    return renderer.render_for_person(person_id, embed_css=embed_css)


def save_census_html(page_id: int, output_path: Path, embed_css: bool = True) -> None:
    """Render and save census page to an HTML file.

    Args:
        page_id: Database page_id
        output_path: Path to save the HTML file
        embed_css: Embed CSS inline (recommended for standalone files)
    """
    html = render_census_page(page_id, embed_css=embed_css)
    output_path.write_text(html)
    logger.info(f"Saved census form to {output_path}")
