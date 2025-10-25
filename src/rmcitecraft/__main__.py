"""Entry point for RMCitecraft application.

This module provides the command-line entry point for the application.
"""

import sys


def main() -> int:
    """Main entry point for rmcitecraft command.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    # Import and run the CLI
    from rmcitecraft.cli import cli_main

    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
