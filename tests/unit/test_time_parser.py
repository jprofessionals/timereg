"""Tests for time string parser."""

import warnings

import pytest

from timereg.core.time_parser import parse_time


class TestValidFormats:
    @pytest.mark.parametrize(
        ("input_str", "expected"),
        [
            ("2h30m", 2.5),
            ("2h", 2.0),
            ("30m", 0.5),
            ("90m", 1.5),
            ("1.5", 1.5),
            ("4.25", 4.25),
            ("0.5", 0.5),
            ("1h45m", 1.75),
            ("8h", 8.0),
            ("1h1m", 1 + 1 / 60),
            ("15m", 0.25),
        ],
    )
    def test_parse_valid_time(self, input_str: str, expected: float) -> None:
        assert parse_time(input_str) == pytest.approx(expected)


class TestInvalidFormats:
    @pytest.mark.parametrize(
        "input_str",
        [
            "",
            "abc",
            "-1h",
            "0h",
            "0m",
            "0",
            "0.0",
            "h30m",
            "hm",
        ],
    )
    def test_reject_invalid_time(self, input_str: str) -> None:
        with pytest.raises(ValueError):
            parse_time(input_str)


class TestEdgeCases:
    def test_large_value_warns(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = parse_time("25h")
            assert result == 25.0
            assert len(w) == 1
            assert "25.0" in str(w[0].message)

    def test_whitespace_stripped(self) -> None:
        assert parse_time("  2h30m  ") == 2.5
