"""Dedicated LLM interaction logger.

Logs all prompts, responses, and metadata to a separate log file
for analysis and debugging of LLM interactions.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

# Configure dedicated LLM log file
LLM_LOG_DIR = Path.home() / ".rmcitecraft" / "logs"
LLM_LOG_FILE = LLM_LOG_DIR / "llm_interactions.log"

# Ensure log directory exists
LLM_LOG_DIR.mkdir(parents=True, exist_ok=True)

# Create a separate logger for LLM interactions
llm_logger = logger.bind(name="llm_interactions")

# Add file handler for LLM-specific logging
logger.add(
    LLM_LOG_FILE,
    filter=lambda record: record["extra"].get("name") == "llm_interactions",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message}",
    rotation="10 MB",
    retention="30 days",
    level="DEBUG",
)


def log_llm_request(
    provider: str,
    model: str,
    prompt: str,
    image_path: str | None = None,
    options: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> str:
    """Log an LLM request before sending.

    Args:
        provider: LLM provider name (e.g., "llm", "openrouter")
        model: Model name/ID
        prompt: The full prompt text
        image_path: Path to image if vision request
        options: Additional options (temperature, etc.)
        context: Additional context (census_year, target_names, etc.)

    Returns:
        Request ID for correlation with response
    """
    request_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    llm_logger.info("=" * 80)
    llm_logger.info(f"LLM REQUEST: {request_id}")
    llm_logger.info(f"Timestamp: {datetime.now().isoformat()}")
    llm_logger.info(f"Provider: {provider}")
    llm_logger.info(f"Model: {model}")
    llm_logger.info(f"Image: {image_path or 'None'}")
    llm_logger.info(f"Options: {json.dumps(options or {})}")
    llm_logger.info(f"Context: {json.dumps(context or {})}")
    llm_logger.info("-" * 40)
    llm_logger.info("PROMPT:")
    llm_logger.info(prompt)
    llm_logger.info("=" * 80)

    return request_id


def log_llm_response(
    request_id: str,
    response_text: str,
    tokens_used: int | None = None,
    duration_seconds: float | None = None,
    metadata: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """Log an LLM response after receiving.

    Args:
        request_id: Request ID from log_llm_request
        response_text: The full response text
        tokens_used: Total tokens consumed
        duration_seconds: Request duration
        metadata: Additional response metadata
        error: Error message if request failed
    """
    llm_logger.info("=" * 80)
    llm_logger.info(f"LLM RESPONSE: {request_id}")
    llm_logger.info(f"Timestamp: {datetime.now().isoformat()}")

    if error:
        llm_logger.error(f"ERROR: {error}")
    else:
        llm_logger.info(f"Duration: {duration_seconds:.2f}s" if duration_seconds else "Duration: N/A")
        llm_logger.info(f"Tokens: {tokens_used or 'N/A'}")
        llm_logger.info(f"Response length: {len(response_text)} chars")
        if metadata:
            llm_logger.info(f"Metadata: {json.dumps(metadata)}")
        llm_logger.info("-" * 40)
        llm_logger.info("RESPONSE:")
        llm_logger.info(response_text)

    llm_logger.info("=" * 80)


def log_llm_validation(
    request_id: str,
    validation_warnings: list[str],
    parsed_records: int = 0,
) -> None:
    """Log validation results for an LLM response.

    Args:
        request_id: Request ID for correlation
        validation_warnings: List of validation warning messages
        parsed_records: Number of records successfully parsed
    """
    llm_logger.info(f"VALIDATION: {request_id}")
    llm_logger.info(f"Records parsed: {parsed_records}")
    llm_logger.info(f"Warnings: {len(validation_warnings)}")

    if validation_warnings:
        llm_logger.warning("Validation warnings:")
        for warning in validation_warnings[:50]:  # Limit to first 50
            llm_logger.warning(f"  - {warning}")
        if len(validation_warnings) > 50:
            llm_logger.warning(f"  ... and {len(validation_warnings) - 50} more")


def get_log_file_path() -> Path:
    """Get the path to the LLM log file."""
    return LLM_LOG_FILE


def tail_log(lines: int = 100) -> str:
    """Get the last N lines of the LLM log.

    Args:
        lines: Number of lines to return

    Returns:
        Last N lines of the log file
    """
    if not LLM_LOG_FILE.exists():
        return "Log file not found"

    with open(LLM_LOG_FILE, "r") as f:
        all_lines = f.readlines()
        return "".join(all_lines[-lines:])
