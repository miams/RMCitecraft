"""Templates package for RMCitecraft HTML templates."""

from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent


def get_template_path(template_name: str) -> Path:
    """Get the path to a template file.

    Args:
        template_name: Name of template file (e.g., 'census/1950_census_form.html')

    Returns:
        Path to the template file

    Raises:
        FileNotFoundError: If template doesn't exist
    """
    template_path = TEMPLATES_DIR / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_name}")
    return template_path
