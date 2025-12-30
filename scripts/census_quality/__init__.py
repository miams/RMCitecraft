"""Census Quality Check package.

Provides comprehensive quality checking for Federal Census sources
in RootsMagic databases.

Public API:
    run_quality_check: Main function to run quality checks
    format_text_output: Human-readable output
    format_compact_output: Token-efficient output for LLMs
    build_census_configs: Get all year configurations
"""

from .configs import build_census_configs
from .formatters import format_compact_output, format_text_output
from .runner import run_quality_check

__all__ = [
    "run_quality_check",
    "format_text_output",
    "format_compact_output",
    "build_census_configs",
]
