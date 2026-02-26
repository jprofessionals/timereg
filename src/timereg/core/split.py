"""Proportional time split calculation across projects."""

from __future__ import annotations

import math
from typing import NamedTuple

from timereg.core.models import SuggestedSplitEntry


class ProjectMetrics(NamedTuple):
    """Commit and line-change metrics for a single project."""

    project_slug: str
    project_name: str
    commit_count: int
    total_insertions: int
    total_deletions: int


def round_to_nearest(hours: float, minutes: int) -> float:
    """Round hours to the nearest interval defined by minutes.

    Examples: round_to_nearest(2.33, 30) → 2.5, round_to_nearest(2.33, 15) → 2.25
    """
    if minutes <= 0:
        return hours
    step = minutes / 60.0
    return round(math.floor(hours / step + 0.5) * step, 4)


def calculate_split(
    project_metrics: list[ProjectMetrics],
    total_hours: float,
    overrides: dict[str, float] | None = None,
    rounding_minutes: int = 0,
) -> list[SuggestedSplitEntry]:
    """Calculate a proportional time split across projects.

    Weight per project = 0.5 * (commits / total_commits) + 0.5 * (lines / total_lines).

    If overrides are provided, those projects are locked at the given hours and
    the remaining hours are redistributed proportionally among non-overridden projects.
    """
    if not project_metrics:
        return []

    overrides = overrides or {}
    # Filter out overrides for projects not in the metrics list
    known_slugs = {m.project_slug for m in project_metrics}
    overrides = {slug: hours for slug, hours in overrides.items() if slug in known_slugs}

    # Calculate raw weights for all projects
    raw_weights = _compute_raw_weights(project_metrics)

    # Apply overrides: lock overridden projects, redistribute remaining hours
    locked_hours = sum(overrides.values())
    remaining_hours = max(total_hours - locked_hours, 0.0)

    # Calculate weights for non-overridden projects
    non_overridden_total_weight = sum(
        w
        for m, w in zip(project_metrics, raw_weights, strict=True)
        if m.project_slug not in overrides
    )

    result: list[SuggestedSplitEntry] = []
    raw_hours: list[float] = []

    for metrics, raw_weight in zip(project_metrics, raw_weights, strict=True):
        if metrics.project_slug in overrides:
            hours = overrides[metrics.project_slug]
            weight = hours / total_hours if total_hours > 0 else 0.0
        elif non_overridden_total_weight > 0:
            proportion = raw_weight / non_overridden_total_weight
            hours = proportion * remaining_hours
            weight = hours / total_hours if total_hours > 0 else 0.0
        else:
            hours = 0.0
            weight = 0.0
        raw_hours.append(hours)
        result.append(
            SuggestedSplitEntry(
                project_slug=metrics.project_slug,
                project_name=metrics.project_name,
                suggested_hours=round(hours, 2),
                weight=round(weight, 4),
                commit_count=metrics.commit_count,
                total_insertions=metrics.total_insertions,
                total_deletions=metrics.total_deletions,
            )
        )

    # Clamp non-overridden entries to 0 (can go negative if overrides exceed total)
    for entry in result:
        if entry.project_slug not in overrides and entry.suggested_hours < 0:
            entry.suggested_hours = 0.0
            entry.weight = 0.0

    # Apply interval rounding to non-overridden entries (e.g. nearest 30min)
    if rounding_minutes > 0:
        for entry in result:
            if entry.project_slug not in overrides:
                entry.suggested_hours = round_to_nearest(entry.suggested_hours, rounding_minutes)

    # Fix rounding so sum equals total_hours exactly
    _fix_rounding(result, total_hours, overrides, rounding_minutes)

    return result


def _compute_raw_weights(metrics_list: list[ProjectMetrics]) -> list[float]:
    """Compute the blended weight for each project (0.5 * commit_ratio + 0.5 * lines_ratio)."""
    total_commits = sum(m.commit_count for m in metrics_list)
    total_lines = sum(m.total_insertions + m.total_deletions for m in metrics_list)

    weights: list[float] = []
    for m in metrics_list:
        commit_ratio = m.commit_count / total_commits if total_commits > 0 else 0.0
        lines = m.total_insertions + m.total_deletions
        lines_ratio = lines / total_lines if total_lines > 0 else 0.0
        weights.append(0.5 * commit_ratio + 0.5 * lines_ratio)

    return weights


def _fix_rounding(
    entries: list[SuggestedSplitEntry],
    total_hours: float,
    overrides: dict[str, float],
    rounding_minutes: int = 0,
) -> None:
    """Adjust the largest non-overridden entry so the sum equals total_hours exactly."""
    current_total = sum(e.suggested_hours for e in entries)
    remainder = round(total_hours - current_total, 2)
    if remainder == 0.0:
        return

    # Find the largest non-overridden entry to absorb the rounding difference
    best_idx = -1
    best_hours = -1.0
    for i, entry in enumerate(entries):
        if entry.project_slug not in overrides and entry.suggested_hours > best_hours:
            best_hours = entry.suggested_hours
            best_idx = i

    if best_idx >= 0:
        adjusted = round(entries[best_idx].suggested_hours + remainder, 2)
        entries[best_idx].suggested_hours = max(adjusted, 0.0)
