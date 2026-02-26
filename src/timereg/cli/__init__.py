"""CLI package — shared utilities for Typer commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from timereg.core.models import Entry


def entry_to_dict(entry: Entry) -> dict[str, object]:
    """Convert an Entry to a JSON-serialisable dict."""
    d = entry.model_dump()
    d["date"] = str(d["date"])
    if d.get("created_at"):
        d["created_at"] = str(d["created_at"])
    if d.get("updated_at"):
        d["updated_at"] = str(d["updated_at"])
    return d
