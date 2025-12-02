"""Census form templates for RMCitecraft."""

from pathlib import Path

CENSUS_TEMPLATES_DIR = Path(__file__).parent


def get_census_form_template(year: int) -> Path:
    """Get the path to a census form template for a specific year.

    Args:
        year: Census year (e.g., 1950)

    Returns:
        Path to the census form HTML template

    Raises:
        FileNotFoundError: If template for that year doesn't exist
    """
    template_path = CENSUS_TEMPLATES_DIR / f"{year}_census_form.html"
    if not template_path.exists():
        raise FileNotFoundError(f"Census form template not found for year {year}")
    return template_path


def list_available_census_templates() -> list[int]:
    """List all available census year templates.

    Returns:
        List of years for which templates exist
    """
    years = []
    for file in CENSUS_TEMPLATES_DIR.glob("*_census_form.html"):
        try:
            year = int(file.stem.split("_")[0])
            years.append(year)
        except (ValueError, IndexError):
            continue
    return sorted(years)
