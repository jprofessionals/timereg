"""Parse human-friendly time strings to float hours."""

from __future__ import annotations

import re
import warnings

_HOURS_MINUTES_RE = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?$")


def parse_time(value: str) -> float:
    """Parse a time string into float hours.

    Supported formats:
        - "2h30m", "2h", "30m", "1h45m" (hours and/or minutes)
        - "1.5", "4.25" (decimal hours)

    Raises ValueError for invalid or non-positive values.
    Warns for values exceeding 24 hours.
    """
    value = value.strip()
    if not value:
        msg = "Time value cannot be empty"
        raise ValueError(msg)

    # Try decimal format first
    try:
        hours = float(value)
        if hours <= 0:
            msg = f"Time must be positive, got {hours}"
            raise ValueError(msg)
        if hours > 24:
            warnings.warn(f"Time value {hours} exceeds 24 hours", stacklevel=2)
        return hours
    except ValueError:
        if re.match(r"^-?\d*\.?\d+$", value):
            raise

    # Try hours/minutes format
    match = _HOURS_MINUTES_RE.match(value)
    if not match:
        msg = f"Invalid time format: {value!r}"
        raise ValueError(msg)

    h_str, m_str = match.groups()
    h = int(h_str) if h_str else 0
    m = int(m_str) if m_str else 0

    if h == 0 and m == 0:
        msg = "Time must be positive"
        raise ValueError(msg)

    hours = h + m / 60
    if hours > 24:
        warnings.warn(f"Time value {hours} exceeds 24 hours", stacklevel=2)
    return hours
