"""Time parsing utilities for Meridian."""

import re
from typing import Optional


class InvalidSLAFormatError(ValueError):
    """Raised when an SLA string cannot be parsed."""

    pass


def parse_duration_to_ms(duration: str) -> int:
    """
    Parse a human-readable duration string into milliseconds.

    Supported formats:
        - "30s" -> 30 seconds -> 30000 ms
        - "5m" -> 5 minutes -> 300000 ms
        - "1h" -> 1 hour -> 3600000 ms
        - "1d" -> 1 day -> 86400000 ms
        - "500ms" -> 500 milliseconds -> 500 ms

    Args:
        duration: A string like "5m", "30s", "1h", "1d", or "500ms"

    Returns:
        Duration in milliseconds

    Raises:
        InvalidSLAFormatError: If the format is invalid
    """
    if not duration:
        raise InvalidSLAFormatError("Duration string cannot be empty")

    duration = duration.strip().lower()

    # Match patterns like "5m", "30s", "1h", "1d", "500ms"
    pattern = r"^(\d+(?:\.\d+)?)(ms|s|m|h|d)$"
    match = re.match(pattern, duration)

    if not match:
        raise InvalidSLAFormatError(
            f"Invalid duration format: '{duration}'. "
            "Expected format like '30s', '5m', '1h', '1d', or '500ms'"
        )

    value = float(match.group(1))
    unit = match.group(2)

    multipliers = {
        "ms": 1,
        "s": 1000,
        "m": 60 * 1000,
        "h": 60 * 60 * 1000,
        "d": 24 * 60 * 60 * 1000,
    }

    return int(value * multipliers[unit])


def format_ms_to_human(ms: int) -> str:
    """
    Format milliseconds into a human-readable string.

    Args:
        ms: Duration in milliseconds

    Returns:
        Human-readable string like "5m 30s" or "1h 2m"
    """
    if ms < 1000:
        return f"{ms}ms"

    seconds = ms // 1000
    if seconds < 60:
        return f"{seconds}s"

    minutes = seconds // 60
    remaining_seconds = seconds % 60
    if minutes < 60:
        if remaining_seconds > 0:
            return f"{minutes}m {remaining_seconds}s"
        return f"{minutes}m"

    hours = minutes // 60
    remaining_minutes = minutes % 60
    if hours < 24:
        if remaining_minutes > 0:
            return f"{hours}h {remaining_minutes}m"
        return f"{hours}h"

    days = hours // 24
    remaining_hours = hours % 24
    if remaining_hours > 0:
        return f"{days}d {remaining_hours}h"
    return f"{days}d"


def validate_sla(sla: Optional[str]) -> Optional[int]:
    """
    Validate and parse an SLA string.

    Args:
        sla: The SLA string to validate, or None

    Returns:
        The SLA in milliseconds, or None if sla is None

    Raises:
        InvalidSLAFormatError: If the SLA format is invalid
    """
    if sla is None:
        return None
    return parse_duration_to_ms(sla)
