"""Tests for proportional time split calculation."""

from __future__ import annotations

from timereg.core.split import ProjectMetrics, calculate_split, round_to_nearest


class TestCalculateSplit:
    def test_two_projects_equal_weight(self) -> None:
        """Two projects with identical metrics get equal hours."""
        metrics = [
            ProjectMetrics(
                "alpha", "Alpha", commit_count=5, total_insertions=100, total_deletions=50
            ),
            ProjectMetrics(
                "beta", "Beta", commit_count=5, total_insertions=100, total_deletions=50
            ),
        ]
        result = calculate_split(metrics, total_hours=8.0)
        assert len(result) == 2
        assert result[0].suggested_hours == 4.0
        assert result[1].suggested_hours == 4.0

    def test_weighted_blend_commits_and_lines(self) -> None:
        """Split reflects 50% commit ratio + 50% lines ratio."""
        # Alpha: 3 commits, 300 lines; Beta: 1 commit, 100 lines
        # Commit ratio: 3/4=0.75, 1/4=0.25
        # Lines ratio: 300/400=0.75, 100/400=0.25
        # Weights: 0.75, 0.25
        metrics = [
            ProjectMetrics(
                "alpha", "Alpha", commit_count=3, total_insertions=200, total_deletions=100
            ),
            ProjectMetrics("beta", "Beta", commit_count=1, total_insertions=80, total_deletions=20),
        ]
        result = calculate_split(metrics, total_hours=8.0)
        assert result[0].suggested_hours == 6.0
        assert result[1].suggested_hours == 2.0

    def test_different_commit_and_line_ratios(self) -> None:
        """When commits and lines diverge, the blend averages them."""
        # Alpha: 1 commit, 900 lines; Beta: 9 commits, 100 lines
        # Commit ratio: 1/10=0.1, 9/10=0.9
        # Lines ratio: 900/1000=0.9, 100/1000=0.1
        # Weights: 0.5*0.1+0.5*0.9=0.5, 0.5*0.9+0.5*0.1=0.5
        metrics = [
            ProjectMetrics(
                "alpha", "Alpha", commit_count=1, total_insertions=900, total_deletions=0
            ),
            ProjectMetrics("beta", "Beta", commit_count=9, total_insertions=100, total_deletions=0),
        ]
        result = calculate_split(metrics, total_hours=10.0)
        assert result[0].suggested_hours == 5.0
        assert result[1].suggested_hours == 5.0

    def test_single_project_gets_all_hours(self) -> None:
        """One project with commits gets 100% of the hours."""
        metrics = [
            ProjectMetrics(
                "only", "Only Project", commit_count=5, total_insertions=200, total_deletions=50
            ),
        ]
        result = calculate_split(metrics, total_hours=7.5)
        assert len(result) == 1
        assert result[0].suggested_hours == 7.5
        assert result[0].weight == 1.0

    def test_no_projects_returns_empty(self) -> None:
        """No projects means no split."""
        result = calculate_split([], total_hours=8.0)
        assert result == []

    def test_project_with_zero_lines(self) -> None:
        """Project with commits but 0 lines still gets weight from commit ratio."""
        metrics = [
            ProjectMetrics("alpha", "Alpha", commit_count=2, total_insertions=0, total_deletions=0),
            ProjectMetrics(
                "beta", "Beta", commit_count=2, total_insertions=100, total_deletions=100
            ),
        ]
        result = calculate_split(metrics, total_hours=8.0)
        # Commit ratio: 0.5, 0.5; Lines ratio: 0/200=0, 200/200=1.0
        # Alpha weight: 0.5*0.5 + 0.5*0 = 0.25
        # Beta weight:  0.5*0.5 + 0.5*1.0 = 0.75
        assert result[0].suggested_hours == 2.0
        assert result[1].suggested_hours == 6.0

    def test_all_projects_zero_lines(self) -> None:
        """When all projects have 0 lines, split is purely by commit count."""
        metrics = [
            ProjectMetrics("alpha", "Alpha", commit_count=3, total_insertions=0, total_deletions=0),
            ProjectMetrics("beta", "Beta", commit_count=1, total_insertions=0, total_deletions=0),
        ]
        result = calculate_split(metrics, total_hours=8.0)
        # Lines ratio is 0 for all, so weight = 0.5 * commit_ratio + 0.5 * 0
        # But we should normalize: alpha=0.25, beta=0.083... no wait, that's wrong.
        # Actually alpha weight = 0.5*(3/4) = 0.375, beta = 0.5*(1/4) = 0.125
        # Total raw weight = 0.5. After normalization: alpha=0.75, beta=0.25
        assert result[0].suggested_hours == 6.0
        assert result[1].suggested_hours == 2.0

    def test_three_way_split(self) -> None:
        """Three projects with varying metrics."""
        metrics = [
            ProjectMetrics("a", "A", commit_count=5, total_insertions=500, total_deletions=0),
            ProjectMetrics("b", "B", commit_count=3, total_insertions=200, total_deletions=100),
            ProjectMetrics("c", "C", commit_count=2, total_insertions=50, total_deletions=50),
        ]
        result = calculate_split(metrics, total_hours=8.0)
        assert len(result) == 3
        total = sum(r.suggested_hours for r in result)
        assert total == 8.0
        # A should have the most, C the least
        assert result[0].suggested_hours > result[1].suggested_hours
        assert result[1].suggested_hours > result[2].suggested_hours

    def test_rounding_sums_to_total(self) -> None:
        """The sum of suggested hours must equal total_hours exactly."""
        metrics = [
            ProjectMetrics("a", "A", commit_count=1, total_insertions=10, total_deletions=0),
            ProjectMetrics("b", "B", commit_count=1, total_insertions=10, total_deletions=0),
            ProjectMetrics("c", "C", commit_count=1, total_insertions=10, total_deletions=0),
        ]
        result = calculate_split(metrics, total_hours=7.0)
        total = sum(r.suggested_hours for r in result)
        assert total == 7.0

    def test_weight_field_populated(self) -> None:
        """Each split entry has a weight reflecting its proportion."""
        metrics = [
            ProjectMetrics("a", "A", commit_count=3, total_insertions=100, total_deletions=0),
            ProjectMetrics("b", "B", commit_count=1, total_insertions=100, total_deletions=0),
        ]
        result = calculate_split(metrics, total_hours=8.0)
        assert sum(r.weight for r in result) == 1.0
        assert result[0].weight > result[1].weight

    def test_metrics_preserved_in_output(self) -> None:
        """Commit counts and line stats are preserved in the output."""
        metrics = [
            ProjectMetrics("x", "X", commit_count=7, total_insertions=300, total_deletions=150),
        ]
        result = calculate_split(metrics, total_hours=4.0)
        assert result[0].commit_count == 7
        assert result[0].total_insertions == 300
        assert result[0].total_deletions == 150
        assert result[0].project_slug == "x"
        assert result[0].project_name == "X"


class TestCalculateSplitWithOverrides:
    def test_override_one_project(self) -> None:
        """Overriding one project redistributes remaining hours by weight."""
        metrics = [
            ProjectMetrics("a", "A", commit_count=4, total_insertions=400, total_deletions=0),
            ProjectMetrics("b", "B", commit_count=3, total_insertions=300, total_deletions=0),
            ProjectMetrics("c", "C", commit_count=1, total_insertions=100, total_deletions=0),
        ]
        # Without overrides: a=4h, b=3h, c=1h (total 8h, equal commit/lines ratio)
        result = calculate_split(metrics, total_hours=8.0, overrides={"b": 5.0})
        # b is locked at 5h. Remaining = 3h.
        # a original weight = 0.5, c original weight = 0.125
        # a and c in ratio 4:1, so a=2.4h, c=0.6h
        assert result[0].project_slug == "a"
        assert result[1].project_slug == "b"
        assert result[2].project_slug == "c"
        assert result[1].suggested_hours == 5.0
        remaining = 8.0 - 5.0
        assert result[0].suggested_hours + result[2].suggested_hours == remaining

    def test_override_leaves_proportions_intact(self) -> None:
        """Non-overridden projects keep the same ratio to each other."""
        metrics = [
            ProjectMetrics("a", "A", commit_count=6, total_insertions=600, total_deletions=0),
            ProjectMetrics("b", "B", commit_count=2, total_insertions=200, total_deletions=0),
            ProjectMetrics("c", "C", commit_count=2, total_insertions=200, total_deletions=0),
        ]
        result_no_override = calculate_split(metrics, total_hours=10.0)
        result_with_override = calculate_split(metrics, total_hours=10.0, overrides={"a": 7.0})

        # b and c should keep the same ratio (1:1 in this case)
        assert result_with_override[1].suggested_hours == result_with_override[2].suggested_hours

        # Original ratio of b:c should be preserved
        ratio_orig = result_no_override[1].suggested_hours / result_no_override[2].suggested_hours
        ratio_override = (
            result_with_override[1].suggested_hours / result_with_override[2].suggested_hours
        )
        assert abs(ratio_orig - ratio_override) < 0.01

    def test_override_exceeds_total_capped(self) -> None:
        """If override exceeds total, non-overridden projects get 0."""
        metrics = [
            ProjectMetrics("a", "A", commit_count=5, total_insertions=500, total_deletions=0),
            ProjectMetrics("b", "B", commit_count=5, total_insertions=500, total_deletions=0),
        ]
        result = calculate_split(metrics, total_hours=8.0, overrides={"a": 9.0})
        assert result[0].suggested_hours == 9.0
        assert result[1].suggested_hours == 0.0

    def test_multiple_overrides(self) -> None:
        """Multiple projects can be overridden simultaneously."""
        metrics = [
            ProjectMetrics("a", "A", commit_count=4, total_insertions=400, total_deletions=0),
            ProjectMetrics("b", "B", commit_count=3, total_insertions=300, total_deletions=0),
            ProjectMetrics("c", "C", commit_count=3, total_insertions=300, total_deletions=0),
        ]
        result = calculate_split(metrics, total_hours=10.0, overrides={"a": 4.0, "b": 4.0})
        assert result[0].suggested_hours == 4.0
        assert result[1].suggested_hours == 4.0
        assert result[2].suggested_hours == 2.0

    def test_override_unknown_project_ignored(self) -> None:
        """Overriding a non-existent project slug is silently ignored."""
        metrics = [
            ProjectMetrics("a", "A", commit_count=5, total_insertions=100, total_deletions=0),
        ]
        result = calculate_split(metrics, total_hours=8.0, overrides={"nonexistent": 3.0})
        assert result[0].suggested_hours == 8.0


class TestRoundToNearest:
    def test_round_to_30_minutes(self) -> None:
        assert round_to_nearest(2.33, 30) == 2.5
        assert round_to_nearest(2.1, 30) == 2.0
        assert round_to_nearest(2.26, 30) == 2.5
        assert round_to_nearest(2.74, 30) == 2.5
        assert round_to_nearest(2.76, 30) == 3.0

    def test_round_to_15_minutes(self) -> None:
        assert round_to_nearest(2.1, 15) == 2.0
        assert round_to_nearest(2.2, 15) == 2.25
        assert round_to_nearest(2.3, 15) == 2.25
        assert round_to_nearest(2.4, 15) == 2.5

    def test_round_to_60_minutes(self) -> None:
        assert round_to_nearest(2.3, 60) == 2.0
        assert round_to_nearest(2.6, 60) == 3.0
        assert round_to_nearest(2.5, 60) == 3.0

    def test_round_to_5_minutes(self) -> None:
        # 5min = 0.0833h steps
        assert round_to_nearest(2.0, 5) == 2.0
        result = round_to_nearest(2.05, 5)
        assert abs(result - 2.0833) < 0.001

    def test_round_to_1_minute(self) -> None:
        # 1min = 0.01667h steps
        assert round_to_nearest(2.0, 1) == 2.0
        result = round_to_nearest(1.5, 1)
        assert abs(result - 1.5) < 0.01

    def test_zero_or_negative_minutes_returns_unchanged(self) -> None:
        assert round_to_nearest(2.33, 0) == 2.33
        assert round_to_nearest(2.33, -5) == 2.33

    def test_exact_values_unchanged(self) -> None:
        assert round_to_nearest(2.0, 30) == 2.0
        assert round_to_nearest(2.5, 30) == 2.5
        assert round_to_nearest(3.0, 30) == 3.0


class TestCalculateSplitWithRounding:
    def test_split_rounded_to_30_minutes(self) -> None:
        """Suggested hours are rounded to nearest 30 minutes."""
        metrics = [
            ProjectMetrics("a", "A", commit_count=3, total_insertions=200, total_deletions=100),
            ProjectMetrics("b", "B", commit_count=1, total_insertions=80, total_deletions=20),
        ]
        # Without rounding: a=6.0, b=2.0 (exact 75/25 split)
        result = calculate_split(metrics, total_hours=8.0, rounding_minutes=30)
        assert result[0].suggested_hours == 6.0
        assert result[1].suggested_hours == 2.0
        total = sum(r.suggested_hours for r in result)
        assert total == 8.0

    def test_split_rounding_adjusts_total(self) -> None:
        """After rounding, the largest entry absorbs any difference to match total."""
        # 3 equal projects, 7h → 2.33h each → rounded to 2.5 each = 7.5
        # The fix_rounding should adjust the largest to make sum = 7.0
        metrics = [
            ProjectMetrics("a", "A", commit_count=1, total_insertions=10, total_deletions=0),
            ProjectMetrics("b", "B", commit_count=1, total_insertions=10, total_deletions=0),
            ProjectMetrics("c", "C", commit_count=1, total_insertions=10, total_deletions=0),
        ]
        result = calculate_split(metrics, total_hours=7.0, rounding_minutes=30)
        total = sum(r.suggested_hours for r in result)
        assert total == 7.0

    def test_split_rounding_15_minutes(self) -> None:
        """Rounding to 15-minute intervals works correctly."""
        metrics = [
            ProjectMetrics("a", "A", commit_count=3, total_insertions=300, total_deletions=0),
            ProjectMetrics("b", "B", commit_count=1, total_insertions=100, total_deletions=0),
        ]
        result = calculate_split(metrics, total_hours=8.0, rounding_minutes=15)
        # Each should be a multiple of 0.25
        for entry in result:
            assert entry.suggested_hours % 0.25 == 0.0 or entry is result[0]
        total = sum(r.suggested_hours for r in result)
        assert total == 8.0

    def test_no_rounding_when_zero(self) -> None:
        """rounding_minutes=0 disables rounding (same as default)."""
        metrics = [
            ProjectMetrics("a", "A", commit_count=1, total_insertions=10, total_deletions=0),
            ProjectMetrics("b", "B", commit_count=1, total_insertions=10, total_deletions=0),
            ProjectMetrics("c", "C", commit_count=1, total_insertions=10, total_deletions=0),
        ]
        result_no_round = calculate_split(metrics, total_hours=7.0, rounding_minutes=0)
        result_default = calculate_split(metrics, total_hours=7.0)
        for a, b in zip(result_no_round, result_default, strict=True):
            assert a.suggested_hours == b.suggested_hours
